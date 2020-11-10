import time
import busio
import digitalio
import board
import threading
import RPi.GPIO as GPIO
import adafruit_mcp3xxx.mcp3008 as MCP
import RPi.GPIO as GPIO
import time
import ES2EEPROMUtils
from adafruit_mcp3xxx.analog_in import AnalogIn

chan_ldr = None                  # ldr channel
chan_temp = None                 # temp sensor channel
btn = 23                         # button pin (BCM)
samplingRate = {0:5, 1:10, 2:15}  # sampling rates
rate = 0                         # current sampling rate position
start_time = 0                   # program start time

eeprom = ES2EEPROMUtils.ES2EEPROM() # eeprom object to handle storage
temp_data = []                      # recent temperature readings (limit is 20)
light_data = []                     # recent light readings (limit is 10) 

# Headings
runtime = 'Runtime'
read = "Reading"
temp = "Temp"
lr = "LDR Reading"
lv = "LDR Voltage"

def unpack(num):
    return num//255, num%255

def pack(H, L):
    return H*255 + L

def fetch_values():
    '''
    Fetches values from the eeprom

    :returns: counts for temperature and light readings, arrays with temmperature and light readings
    '''
    temp_count = eeprom.read_byte(0)
    light_count = eeprom.read_byte(1)

    temp_raw = eeprom.read_block(1, temp_count * 5)

    light_start = temp_count + 1
    light_raw = eeprom.read_block( light_start, light_count * 5 )

    temp_values = []
    for i in range(0, len(temp_raw), 5):
        time = "{:02d}:{:02d}:{:02d}".format( temp_raw[i], temp_raw[i + 1], temp_raw[i + 2])
        temp_val = temp_raw[i + 3]
        temp_values.append( [time, temp_val] )
    
    light_values = []
    for i in range(0, len(light_raw), 5):
        time = "{:02d}:{:02d}:{:02d}".format( light_raw[i], light_raw[i + 1], light_raw[i + 2])
        light_val = temp_raw[ i + 3]
        light_values.append( [time, temp_val] )

    return temp_count, light_count, temp_values, light_values

def save_values( temp_arr, light_arr):
    """
    Saves temperature and light values to the eeprom

    :param temp_value: the temperature value to write
    :param light_value: the light value to write
    """
    # update the data arrays
    global temp_data
    global light_data

    if (len(temp_data) < 20):
        
        temp_data = [temp_arr] + temp_data
    else:
        temp_data = [temp_arr] + temp_data[:-1]
    
    if (len(light_data) < 20):
        light_data = [light_arr] + light_data
    else:
        light_data = [light_arr] + light_data[:-1]
    
    temp_length = len(temp_data)
    light_length = len(light_data)
    
    # write temp
    data_to_write = []
    for data in temp_data:
        time_arr = data[0].split(":")
        for i in time_arr:
            data_to_write.append(int(i))
        data_to_write.append(data[1])
        
    for data in light_data:
        time_arr = data[0].split(":")
        for i in time_arr:
            data_to_write.append(int(i))
        data_to_write.append(data[1])
    
    eeprom.write_block(0, [temp_length, light_length])
    eeprom.write_block(1, data_to_write)

def clear_values():
    """
    Clears all eeprom data
    """
    eeprom.clear(32)

def values_thread():
    # create the thread to run after a delay from the sampling rate
    thread = threading.Timer(samplingRate[rate], values_thread)
    thread.daemon = True
    thread.start()

    # update runtime
    current_time = int( time.time() - start_time )

    # Displaying ldr and temp readings
    str_runtime = str(current_time) + "s"
    str_tempValue = chan_temp.value
    str_temp = str( round( (chan_temp.voltage - 0.5)/0.01, 2 ) ) + " C"
    str_ldrValue = chan_ldr.value
    str_ldrVoltage = str( round( chan_ldr.voltage, 2 )) + " V"

    save_values([actual_time, temp], [actual_time, lumen])
    
    print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( str_runtime,
                                                        str_tempValue,
                                                        str_temp,
                                                        str_ldrValue,
                                                        str_ldrVoltage))
    
    """
    temp_count, light_count, temp_values, light_values = fetch_values()
    print("temp_count: "+ str(temp_count))
    print(temp_values)
    print("light_count: "+ str(light_count))
    print(light_values)
    """

def btn_pressed(channel):
    # Update rate
    global rate

    rate = (rate + 1) % 3
    
    print(f"Sampling at : {samplingRate[rate]}s")
    print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))


def setup():

    global chan_ldr
    global chan_temp
    
    # create the spi bus
    spi = busio.SPI( clock = board.SCK, MISO = board.MISO, MOSI = board.MOSI )

    # create the cs (chip select)
    cs = digitalio.DigitalInOut(board.D5)

    # create the mcp object
    mcp = MCP.MCP3008( spi, cs )

    # create an analog input channel on pin 0
    chan_ldr = AnalogIn( mcp, MCP.P0)
    chan_temp = AnalogIn( mcp, MCP.P1)

    # setup button
    GPIO.setup(btn, GPIO.IN)
    GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(btn, GPIO.FALLING, callback=btn_pressed, bouncetime=200)

    # clear storage
    clear_values()


if __name__ == "__main__":
    try:
        setup()

        # program start time.
        start_time = time.time()
        print(f"Sampling at : {samplingRate[rate]}s")
        print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))

        values_thread()
        while True:
            pass
    except KeyboardInterrupt:
        print("\nExiting Gracefully..")
    except Exception as e:
        print(e)
    finally:
        GPIO.cleanup()