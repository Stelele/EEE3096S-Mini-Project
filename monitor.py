import os
import time
import busio
import digitalio
import board
import threading
import RPi.GPIO as GPIO
import adafruit_mcp3xxx.mcp3008 as MCP
import RPi.GPIO as GPIO
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

# Headings
runtime = 'Time'
read = "Sys Timer"
temp = "Temp"
lr = "Lumens"
lv = "Buzzer"

def values_thread():
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

    if stopLogging:
        return

    rate = (rate + 1) % 3
    
    print(f"Sampling at : {samplingRate[rate]}s")
    print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))

def btn_stop_pressed(channel):

    global stopLogging
    global buzzer

    stopLogging = not stopLogging
    
    #inform user of current system status
    os.system('clear')
    print("===================================")

    if stopLogging:
        print(":(\tLogging has stopped\t:(")
        buzzer.stop()
    else:
        print(":)\tLoggin has resumed\t:)")
    
    print("===================================")

    if not stopLogging:
        print(f"Sampling at : {samplingRate[rate]}s")
        print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( runtime, read, temp, lr, lv))

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