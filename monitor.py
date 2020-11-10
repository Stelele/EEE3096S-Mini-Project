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
samplingRate = {0:1, 1:5, 2:10}  # sampling rates
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

def fetch_values():
    '''
    Fetches values from the eeprom

    :returns: counts for temperature and light readings, arrays with temmperature and light readings
    '''
    temp_count = eeprom.read_byte(0)
    light_count = eeprom.read_byte(1)

    temp_start = 2
    temp_stop = temp_start + temp_count * 2
    light_start = temp_stop
    light_stop = light_start + light_count

    temp_values = eeprom.read_2bytes( temp_start, temp_count )
    light_values = eeprom.read_2bytes( light_start, light_count )

    return temp_count, light_count, temp_values, light_values

def save_values( temp_value, light_value):
    """
    Saves temperature and light values to the eeprom

    :param temp_value: the temperature value to write
    :param light_value: the light value to write
    """
    # update the data arrays
    global temp_data
    global light_data

    if (len(temp_data) < 20):
        
        temp_data = [temp_value] + temp_data
    else:
        temp_data = [temp_value] + temp_data[:-1]
    
    if (len(light_data) < 10):
        light_data = [light_value] + light_data
    else:
        light_data = [light_value] + light_data[:-1]
    
    temp_length = len(temp_data)
    light_length = len(light_data)
    temp_start = 2
    light_start = temp_start + temp_length * 2

    # write data lengths to the eeprom
    eeprom.write_byte(0, temp_length)
    eeprom.write_byte(1, light_length)

    # finally, write data to the eeprom
    eeprom.write_2bytes(temp_data, temp_start)
    eeprom.write_2bytes(light_data, light_start)

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

    save_values(chan_temp.value, chan_ldr.value)

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