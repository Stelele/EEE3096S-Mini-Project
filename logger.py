import time
import busio
import digitalio
import board
import threading
import RPi.GPIO as GPIO
import adafruit_mcp3xxx.mcp3008 as MCP
import RPi.GPIO as GPIO
import time
from adafruit_mcp3xxx.analog_in import AnalogIn

chan_ldr = None                  # ldr channel
chan_temp = None                 # temp sensor channel
btn = 23                         # button pin (BCM)
samplingRate = {0:1, 1:5, 2:10}  # sampling rates
rate = 0                         # current sampling rate position
start_time = 0                   # program start time

# Headings
runtime = 'Runtime'
read = "Reading"
temp = "Temp"
lr = "LDR Reading"
lv = "LDR Voltage"

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

    print("{:<15}{:<15}{:<15}{:<15}{:<15}".format( str_runtime,
                                                        str_tempValue,
                                                        str_temp,
                                                        str_ldrValue,
                                                        str_ldrVoltage))


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