# Python library for 4tronix Picon Zero
# Dowloaded from http://4tronix.co.uk/piconzero/piconzero.py
# Note that all I2C accesses are wrapped in try clauses with repeats
# Run through 2to3 and edited by Connor Henley, @thatging3rkid
import sys
import time
import smbus  # note that you have to install smbus using apt
import threading

bus = smbus.SMBus(1)  # For revision 1 Raspberry Pi, change to bus = smbus.SMBus(0)
pzaddr = 0x22  # I2C address of Picon Zero

# Definitions of Commands to Picon Zero
MOTORA = 0
MOTORB = 1
OUTCFG0 = 2
OUTPUT0 = 8
INCFG0 = 14
SETBRIGHT = 18
UPDATENOW = 19
RESET = 20

EXIT_SUCCESS = 0
EXCEEDED_RETRIES = -1
INVALID_RANGE = -2
UNSUPPORTED = -3

# General variables
DEBUG = False
RETRIES = 10  # max number of retries for I2C calls
revision = 255  # is overwritten on init
l = threading.Lock()  # only allow one thread to access the picon

def get_revision():
    """
    Get version and revision info

    :return: the version of the board and the board type in a list
    """
    with l:
        for i in range(RETRIES):
            try:
                rval = bus.read_word_data(pzaddr, 0)
                return [rval / 256, rval % 256]  # firmware is first, board type is second
            except Exception as e:
                if DEBUG:
                    print("error in get_revision(), retrying", file=sys.stderr)
                    print(e, file=sys.stderr)

def set_motor(motor, value):
    """
    Set a motor output

    :param motor: MOTORA or MOTORB (0 or 1)
    :param value: The new value (must be in range -128 to +127)
    :note: values of -127, -128, +127 are treated as always ON, so no PWM
    :return: 0 on success, something else on failure
    """
    with l:
        if motor >= 0 and motor <= 1 and value >= -128 and value < 128:
            for i in range(RETRIES):
                try:
                    bus.write_byte_data(pzaddr, motor, value)
                    return EXIT_SUCCESS  # exit function
                except Exception as e:
                    if DEBUG:
                        print("error in set_motor(), retrying", file=sys.stderr)
                        print(e, file=sys.stderr)

            return EXCEEDED_RETRIES  # return (indicating that retries was exceeded)
        return INVALID_RANGE  # return (indicating error)


def read_input(channel):
    """
     Gets the value of the selected input channel. This will return:
        - 0 (False) or 1 (True) if the channel is Digital
        - A value from 0 to 1023 if the channel is analog
        - A temperature in centigrade if the channel is a DS18B20

    :param channel: channel must be in range 0 to 3
    :return: status code
    """
    with l:
        if channel >= 0 and channel <= 3:
            for i in range(RETRIES):
                try:
                    return bus.read_word_data(pzaddr, channel + 1)
                except Exception as e:
                    if DEBUG:
                        print("error in read_input(), retrying", file=sys.stderr)
                        print(e, file=sys.stderr)
            return EXCEEDED_RETRIES
        return INVALID_RANGE


def set_output_config(output, value):
    """
    This sets the configuration of the selected Output channel. There are 6 Output channels (0 to 5) and these can be set as follows:
        - 0: Digital (Low or High) – this is the Default output configuration
        - 1: PWM (0 to 100% duty cycle)
        - 2: Servo (0 to 180 degrees)
        - 3: Neopixel WS2812B (individually address any pixel and set values of 0..255 for each colour). Only Output channel 5 can be set to this configuration value

    :param output: the channel to set
    :param value: the configuration value
    :return: status code
    """
    with l:
        if output >= 0 and output <= 5 and value >= 0 and value <= 3:
            for i in range(RETRIES):
                try:
                    bus.write_byte_data(pzaddr, OUTCFG0 + output, value)
                    return EXIT_SUCCESS
                except Exception as e:
                    if DEBUG:
                        print("error in set_output_config(), retrying", file=sys.stderr)
                        print(e, file=sys.stderr)
            return EXCEEDED_RETRIES
        return INVALID_RANGE


def set_input_config(channel, value, pullup=False):
    """
    This sets the configuration of the selected Input channel. There are 4 Input channels (0 to 3). The config parameter determines if the channel is:
        - 0: Digital (0 or 1) – this is the Default input configuration
        - 1: Analog (0 to 1023) - read analog values from selected channel. 0V -> 0;  5V -> 1023
        - 2: DS18B20 [Available from firmware revision 06] - reads a 18B20 temperature sensor

    :param channel: the channel to configure
    :param value: the configuration value
    :param pullup: set to False by default, but can be set to True which will provide a 10K internal pullup resistor on the selected channel (firmware 08 and later)
    :return: status code
    """
    with l:
        if channel >= 0 and channel <= 3 and value >= 0 and value <= 3:
            if value == 2 and revision <= 6:
                return UNSUPPORTED
            if value == 0 and pullup == True:
                value = 128
            for i in range(RETRIES):
                try:
                    bus.write_byte_data(pzaddr, INCFG0 + channel, value)
                    return EXIT_SUCCESS
                except Exception as e:
                    if DEBUG:
                        print("error in set_input_config(), retrying", file=sys.stderr)
                        print(e, file=sys.stderr)
            return EXCEEDED_RETRIES
        return INVALID_RANGE


def set_output(channel, value):
    """
    Sets the output channel with the data entered – Digital, PWM and Servo data only.
    Set output data for selected output channel
     Mode  Name    Type    Values
    | 0     On/Off  Byte    0 is OFF, 1 is ON
    | 1     PWM     Byte    0 to 100 percentage of ON time
    | 2     Servo   Byte    -100 to +100 Position in degrees
    | 3     WS2812B 4 Bytes 0:Pixel ID, 1:Red, 2:Green, 3:Blue

    :return: status code
    """
    with l:
        if (channel >= 0 and channel <= 5):
            for i in range(RETRIES):
                try:
                    bus.write_byte_data(pzaddr, OUTPUT0 + channel, value)
                    return EXIT_SUCCESS
                except Exception as e:
                    if DEBUG:
                        print("error in set_output(), retrying", file=sys.stderr)
                        print(e, file=sys.stderr)
            return EXCEEDED_RETRIES
        return INVALID_RANGE


def set_pixel(Pixel, Red, Green, Blue, Update=True):
    """
    Sets the selected pixel with the selected red, green and blue values (0 to 255)

    :param Red: red value
    :param Green: green value
    :param Blue: blue value
    :param Update: update the pixel data immediately (as it takes time)
    :return: status code
    """
    with l:
        pixelData = [Pixel, Red, Green, Blue]
        for i in range(RETRIES):
            try:
                bus.write_i2c_block_data(pzaddr, Update, pixelData)
                return EXIT_SUCCESS
            except Exception as e:
                if DEBUG:
                    print("error in set_pixel(), retrying", file=sys.stderr)
                    print(e, file=sys.stderr)
        return EXCEEDED_RETRIES


def set_all_pixels(Red, Green, Blue, Update=True):
    """
    Sets all pixels with the selected red, green and blue values (0 to 255) [Available from firmware revision 07]

    :param Red: red value
    :param Green: green value
    :param Blue: blue value
    :param Update: update the pixel data immediately (as it takes time)
    :return: status code
    """
    with l:
        if revision < 7:
            return UNSUPPORTED
        pixelData = [100, Red, Green, Blue]
        for i in range(RETRIES):
            try:
                bus.write_i2c_block_data(pzaddr, Update, pixelData)
                return EXIT_SUCCESS
            except Exception as e:
                if DEBUG:
                    print("error in set_all_pixels(), retrying", file=sys.stderr)
                    print(e, file=sys.stderr)
        return EXCEEDED_RETRIES


def update_pixels():
    """
    Causes an immediate update of all the pixels from the latest data

    :return: status code
    """
    with l:
        for i in range(RETRIES):
            try:
                bus.write_byte_data(pzaddr, UPDATENOW, 0)
                return EXIT_SUCCESS
            except Exception as e:
                if DEBUG:
                    print("error in update_pixels(), retrying", file=sys.stderr)
                    print(e, file=sys.stderr)
        return EXCEEDED_RETRIES


def set_brightness(brightness):
    """
    Sets the overall brightness (0 to 255) of the neopixel chain. All RGB values are scaled to fit into this max value.

    :param brightness: the new brightness (range 0 to 255; default is 40)
    :return: status code
    """
    with l:
        for i in range(RETRIES):
            try:
                bus.write_byte_data(pzaddr, SETBRIGHT, brightness)
                return EXIT_SUCCESS
            except Exception as e:
                if DEBUG:
                    print("error in set_brightness(), retrying", file=sys.stderr)
                    print(e, file=sys.stderr)
        return EXCEEDED_RETRIES


def init(debug=False):
    """
    This clears all the Inputs and Outputs back to their default configurations, stops the motors, disables any servos
    and switches off Neopixels. It also sets a few internal variables that allows the Picon Zero to keep track of what it is doing.

    :param debug: debug mode switch
    :return: status code
    """
    DEBUG = debug
    if DEBUG:
        print("Debug enabled", file=sys.stderr)

    for i in range(RETRIES):
        try:
            l.acquire(blocking=True)
            bus.write_byte_data(pzaddr, RESET, 0)
            time.sleep(0.01)  # 10ms delay to allow time to complete
            l.release()
            global revision
            revision = get_revision()[0]  # update the revision number after the board has been initialized
            return EXIT_SUCCESS
        except Exception as e:
            if DEBUG:
                print("error in init(), retrying", file=sys.stderr)
                print(e, file=sys.stderr)
    return EXCEEDED_RETRIES


def cleanup():
    """
    Cleanup the board when done (clears all outputs)

    :return: status code
    """
    with l:
        for i in range(RETRIES):
            try:
                bus.write_byte_data(pzaddr, RESET, 0)
                time.sleep(0.01)  # 10ms delay to allow time to complete
                return EXIT_SUCCESS
            except Exception as e:
                if DEBUG:
                    print("error in cleanup(), retrying", file=sys.stderr)
                    print(e, file=sys.stderr)
        return EXCEEDED_RETRIES
