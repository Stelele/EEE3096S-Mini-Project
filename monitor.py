import os
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
from datetime import datetime

chan_ldr = None                  # ldr channel
chan_temp = None                 # temp sensor channel
buzzer = None                    # buzzer pwn handler
buzzer_pin = 13                  # GPIO pin (BCM) for buzzer
btn_rate = 23                    # button pin (BCM) to change sampling rate
btn_stop = 24                    # button pin (BCM) to stop logging

samplingRate = {0:5, 1:10, 2:15} # sampling rates
rate = 0                         # current sampling rate position
start_time = 0                   # program start time
stopLogging = False              # flag to check if system should log values or not 
threshMin = 24                   # minium allowable temperature
threshMax = 29                   # maximum allowable temperature
programRun = False               # flag to check if logging function is running
long_press_threshold = 1         # time button must be pushed down to register a long press

eeprom = ES2EEPROMUtils.ES2EEPROM() # eeprom object to handle storage
temp_data = []                      # recent temperature readings (limit is 20)
light_data = []                     # recent light readings (limit is 10) 
start_block = 3000

# Headings
runtime = 'Time'
read = "Sys Timer"
temp = "Temp"
lr = "Lumens"
lv = "Buzzer"


def display_values(temp_count, light_count, temp_values, light_values):
    """
    Displays up to the last 20 temperature and lumenous intensity reading
    """

    print(f"There are {temp_count} temperature readings and {light_count} light intensity readings.")
    print("===========================")
    print("Temperature readings")
    print("===========================")
    print("{:<15}{:<15}".format( runtime, temp))

    for i in range (0, len(temp_values)):
        tim = temp_values[i][0]
        val = str(temp_values[i][1]) + " C"
        print("{:<15}{:<15}".format( tim , val ))
    
    print("===========================")
    print("Luminous Intensity readings")
    print("===========================")
    print("{:<15}{:<15}".format( runtime, lr))

    for i in range (0, len(light_values)):
        tim = light_values[i][0]
        val = str(light_values[i][1]) + " lm"
        print("{:<15}{:<15}".format( tim , val ))


def fetch_values():
    '''
    Fetches values from the eeprom

    :returns: counts for temperature and light readings, arrays with temmperature and light readings
    '''
    global temp_data
    global light_data
    
    # counts = eeprom.read_block(1,2)
    # temp_count = counts[0]
    # light_count = counts[1]

    temp_count = eeprom.read_byte(1000)
    light_count = eeprom.read_byte(2000)

    temp_raw = eeprom.read_block(start_block, temp_count * 4)

    light_start = start_block + temp_count + 1
    light_raw = eeprom.read_block( light_start, light_count * 4 )

    temp_values = []
    for i in range(0, len(temp_raw), 4):
        hr = temp_raw[i]
        mn = temp_raw[i + 1]
        sec = temp_raw[i + 2]
        time = "{:02d}:{:02d}:{:02d}".format( hr , mn , sec )
        temp_val = temp_raw[i + 3]
        temp_values.append( [time, temp_val] )
    
    light_values = []
    for i in range(0, len(light_raw), 4):
        hr = light_raw[i]
        mn = light_raw[i + 1]
        sec = light_raw[i + 2]
        time = "{:02d}:{:02d}:{:02d}".format( hr, mn, sec)
        light_val = light_raw[ i + 3]
        light_values.append( [time, temp_val] )

    return temp_count, light_count, temp_values, light_values

def save_values( temp_arr, light_arr):
    """
    Saves temperature and lumenous intensity values to the eeprom
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
    
    eeprom.write_byte(1000, temp_length)
    eeprom.write_byte(2000, light_length)
    time.sleep(0.5)
    eeprom.write_block(start_block, data_to_write)

def clear_values():
    """
    Clears all eeprom data
    """
    eeprom.clear(4096)

def values_thread():
    global programRun

    if not programRun:
        return

    # create the thread to run after a delay from the sampling rate
    thread = threading.Timer(samplingRate[rate], values_thread)
    thread.daemon = True
    thread.start()

    # checking if btn_stop has been pressed and stop program
    if stopLogging:
        return 

    # update runtime
    sys_time = int( time.time() - start_time )
    actual_time = datetime.now().strftime("%H:%M:%S")
    str_runtime = format_time(sys_time)

    #get light intensity and temperature readings from ADC
    temp = round((chan_temp.voltage - 0.5)/0.01)
    ldr_vol = chan_ldr.voltage
    lumen = round((500*(3.3-ldr_vol))/ldr_vol)

    allowable_temp = trigger_buzzer(temp)

    # Displaying ldr and temp readings
    str_temp = str(temp) + " C"
    str_lumen = str(lumen) + ' lm'
    str_buzzer = '' if allowable_temp else '*' 
    
    print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( actual_time,
                                                        str_runtime,
                                                        str_temp,
                                                        str_lumen,
                                                        str_buzzer))

    #save the values
    save_values([actual_time, temp], [actual_time, lumen])

def trigger_buzzer(temp):
    global buzzer
    global threshMax
    global threshMin

    allowableTemp = True
    if temp < threshMin or temp > threshMax:
        allowableTemp = False
        buzzer.start(100)
    else:
        buzzer.stop()

    return allowableTemp

def format_time(sys_time):
    hours = sys_time // 3600
    sys_time = sys_time % 3600
    minutes = sys_time // 60
    seconds = sys_time % 60

    return "{:0>2}:{:0>2}:{:0>2}".format(hours, minutes, seconds)

def btn_rate_pressed(channel):
    # Update rate
    global rate
    global stopLogging
    global programRun

    if stopLogging or not programRun:
        return

    rate = (rate + 1) % 3
    
    print(f"Sampling at : {samplingRate[rate]}s")
    print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))

def btn_stop_pressed(channel):
    global programRun

    if not programRun:
        return

    #check if long press
    startingAt = time.time()
    while GPIO.input(btn_stop) == False:
        time.sleep(0.01)

    timeElapsed = time.time() - startingAt

    if timeElapsed < long_press_threshold: 
        global stopLogging
        global buzzer

        stopLogging = not stopLogging
        
        #inform user of current system status
        os.system('clear')
        print("===================================")

        if stopLogging:
            print(":(\tLogging has stopped\t:(")
        else:
            print(":)\tLoggin has resumed\t:)")
        
        print("===================================")

        if stopLogging == False:
            print(f"Sampling at : {samplingRate[rate]}s")
            print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))
    
    else:
        programRun = False

    buzzer.stop()
    
def welcome():
    print("""
                 __        __       _                                 _            _                                        ____
                 \ \      / /  ___ | |  ___   ___   _ __ ___    ___  | |_   ___   | |      ___    __ _   __ _   ___  _ __  |  _ \  _   _
                  \ \ /\ / /  / _ \| | / __| / _ \ | '_ ` _ \  / _ \ | __| / _ \  | |     / _ \  / _` | / _` | / _ \| '__| | |_) || | | |
                   \ V  V /  |  __/| || (__ | (_) || | | | | ||  __/ | |_ | (_) | | |___ | (_) || (_| || (_| ||  __/| |    |  __/ | |_| |
                    \_/\_/    \___||_| \___| \___/ |_| |_| |_| \___|  \__| \___/  |_____| \___/  \__, | \__, | \___||_|    |_|     \__, |
                                                                                                  |___/  |___/                      |___/
    """)
    print("Select an option:     L - Start Logging       H - See Recording Log      C - Clear Log      Q - Quit")

def setup():

    global chan_ldr
    global chan_temp
    global buzzer
    
    # create the spi bus
    spi = busio.SPI( clock = board.SCK, MISO = board.MISO, MOSI = board.MOSI )

    # create the cs (chip select)
    cs = digitalio.DigitalInOut(board.D5)

    # create the mcp object
    mcp = MCP.MCP3008( spi, cs )

    # create an analog input channel on pin 0
    chan_ldr = AnalogIn( mcp, MCP.P0)
    chan_temp = AnalogIn( mcp, MCP.P1)

    # setup buttons and event detection
    GPIO.setup(btn_rate, GPIO.IN)
    GPIO.setup(btn_stop, GPIO.IN)

    GPIO.setup(btn_rate, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(btn_stop, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.add_event_detect(btn_rate, GPIO.FALLING, callback=btn_rate_pressed, bouncetime=200)
    GPIO.add_event_detect(btn_stop, GPIO.FALLING, callback=btn_stop_pressed, bouncetime=200)

    # setup PWM for buzzer
    GPIO.setup(buzzer_pin, GPIO.OUT)


    buzzer = GPIO.PWM(buzzer_pin, 1)    
    buzzer.stop()

def main():
    global stopLogging
    global programRun
    global start_time

    choice = input()
    choice = choice.lower()
    if choice == 'l':
        # program start time
        programRun = True
        start_time = time.time()
        print(f"Sampling at : {samplingRate[rate]}s")
        print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))
        
        values_thread()
        stopLogging = False

        while programRun:
            pass
        
        os.system('clear')
        welcome()

    elif choice == 'h':
        temp_count, light_count, temp_values, light_values = fetch_values()
        display_values(temp_count, light_count, temp_values, light_values)
    
    elif choice == 'c':
        clear_values()
        print("Cleared!")
    
    elif choice == 'q':
        raise KeyboardInterrupt

    else:
        print("invalid choice selected")


if __name__ == "__main__":
    try:
        setup()
        welcome()
        while True:
            main()            
       
    except KeyboardInterrupt:
        print("\nExiting Gracefully..")
    except Exception as e:
        print(e)
    finally:
        GPIO.cleanup()