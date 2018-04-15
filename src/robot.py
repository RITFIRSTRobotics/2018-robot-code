import os
import sys
import time
import socket
import logging
import jsonpickle
from logging.handlers import RotatingFileHandler

sys.path.append(os.getcwd())  # have to add this for local files
from src.Watchdog import Watchdog

import libs.piconzero as piconzero

from core.network.utils import get_ip
from core.network.Packet import Packet, PacketType
from core.network.constants import *
from core.network.packetdata import MovementData
from core.network.packetdata.RequestData import RequestData
from core.network.packetdata.RobotStateData import RobotStateData


# Some constants
SHOOTER_ROBOT = os.path.isfile(".shooterbot")
GRIPPER_ROBOT0 = os.path.isfile(".gripperbot0")
GRIPPER_ROBOT1 = os.path.isfile(".gripperbot1")
GRIPPER_ROBOT = GRIPPER_ROBOT0 or GRIPPER_ROBOT1

if (SHOOTER_ROBOT and GRIPPER_ROBOT) or (GRIPPER_ROBOT0 and GRIPPER_ROBOT1):
    print("multiple robot subsystems, exiting", file=sys.stderr)
    exit(1)

SHOOTER_MOTOR_CHANNEL = 0

LIFT_SERVO_CHANNEL = 0
GRIP_SERVO_CHANNEL = 1

if SHOOTER_ROBOT:
    SHOOTER_HIGH = 80
    SHOOTER_MID = 40
    SHOOTER_OFF = 0

if GRIPPER_ROBOT0:
    LIFT_SERVO_MIN = 43
    LIFT_SERVO_MAX = 95
    LIFT_SERVO_SPEEDMOD = 32.0
    GRIP_SERVO_MIN = 0
    GRIP_SERVO_MAX = 100

if GRIPPER_ROBOT1:
    LIFT_SERVO_MIN = 0
    LIFT_SERVO_MAX = 50
    LIFT_SERVO_SPEEDMOD = 32.0
    GRIP_SERVO_MIN = 0
    GRIP_SERVO_MAX = 100

lift_servo_pos = LIFT_SERVO_MIN
grip_servo_pos = GRIP_SERVO_MIN
grip_servo_prev = False


def process_data(pack):
    """
    Process a packet's data

    :param pack: a packet with data in it
    """
    global grip_servo_prev, grip_servo_pos, lift_servo_pos

    # See if the data is MovementData
    if type(pack.data) is MovementData.MovementData:
        # bindings for old code
        pack.data.scale()
        s_side, s_forw = pack.data.get_stick0()
        s_side *= -1

        # Calculate motor outputs
        if abs(s_forw) < CONTROLLER_DEADZONE and abs(s_side) < CONTROLLER_DEADZONE:
            # First, check deadzones
            s_forw = 0
            s_side = 0
        else:
            if s_forw > 0:
                if s_side > 0:
                    left_motor = s_forw - s_side
                    right_motor = max(s_forw, s_side)
                else:
                    left_motor = max(s_forw, -s_side)
                    right_motor = s_forw + s_side
            else:
                if s_side > 0:
                    left_motor = -1 * max(-s_forw, s_side)
                    right_motor = s_forw + s_side
                else:
                    left_motor = s_forw - s_side
                    right_motor = -1 * max(-1 * s_forw, -1 * s_side)

        # Range check
        if left_motor >= 0:
            left_motor = min(left_motor, 127)
        else:
            left_motor = max(left_motor, -127)
        if right_motor >= 0:
            right_motor = min(right_motor, 127)
        else:
            right_motor = max(right_motor, -127)

        piconzero.set_motor(piconzero.MOTORA, left_motor)
        piconzero.set_motor(piconzero.MOTORB, right_motor)

    if SHOOTER_ROBOT:
        if pack.data.butttons[2]:
            piconzero.set_output(SHOOTER_MOTOR_CHANNEL, SHOOTER_HIGH)
        elif pack.data.buttons[0]:
            piconzero.set_output(SHOOTER_MOTOR_CHANNEL, SHOOTER_MID)
        else:
            piconzero.set_output(SHOOTER_MOTOR_CHANNEL, SHOOTER_OFF)

    if GRIPPER_ROBOT:
        toggle_button = pack.data.buttons[2]

        # See if the gripper needs to change
        if toggle_button != grip_servo_prev:
            if grip_servo_pos == GRIP_SERVO_MIN:
                grip_servo_pos = GRIP_SERVO_MAX
            else:
                grip_servo_pos = GRIP_SERVO_MIN
            piconzero.set_output(GRIP_SERVO_CHANNEL, grip_servo_pos)

        # Now for the lift servo
        lift_servo_pos += int(pack.data.sticks[2] / LIFT_SERVO_SPEEDMOD)
        if lift_servo_pos > LIFT_SERVO_MAX or lift_servo_pos < LIFT_SERVO_MIN:
            if lift_servo_pos > LIFT_SERVO_MAX:
                lift_servo_pos = LIFT_SERVO_MAX
            else:
                lift_servo_pos = LIFT_SERVO_MIN

        piconzero.set_output(LIFT_SERVO_CHANNEL, lift_servo_pos)
        grip_servo_prev = toggle_button  # save for later


def main():
    # start the logger
    logger = logging.getLogger(__name__)
    handler = RotatingFileHandler('robot_log.log', "a", maxBytes=960000, backupCount=5)
    logger.addHandler(handler)

    # initalize i2c and piconzero
    piconzero.init()

    # Open the socket
    logger.info("opening socket")
    sock = socket.socket()

    # Figure out and log the ip of the robot
#    ip = get_ip()
    ip = "10.0.1.10"
    logger.info("using ip: `" + ip + "`")
    sock.bind((ip, PORT))  # bind it to the socket
    sock.listen(5)  # listen for incoming data

    # Make robot stuff
    robot_disabled = True
    watchdog = Watchdog(logger)

    if SHOOTER_ROBOT:
        piconzero.set_output_config(SHOOTER_MOTOR_CHANNEL, 1)  # set channel 0 to PWM mode
    if GRIPPER_ROBOT:
        piconzero.set_output_config(LIFT_SERVO_CHANNEL, 2)
        piconzero.set_output_config(GRIP_SERVO_CHANNEL, 2)  # set channel 0 and 1 to Servo mode

    # Initialization should be done now, start accepting packets
    while True:
        try:
            # Get a connection
            csock, addr = sock.accept()
            pack = jsonpickle.decode(csock.recv(BUFFER_SIZE).decode())  # recieve packets, decode them, then de-json them
            watchdog.reset()

            # Type-check the data
            if type(pack) is not Packet:
                print("pack is not a Packet", file=sys.stderr)
                continue

            # Process the packet
            if pack.type == PacketType.STATUS:
                # Check the contents of the packet
                if type(pack.data) is RobotStateData:
                    if pack.data == RobotStateData.ENABLE:
                        robot_disabled = False

                        # Reinitialize the picon zero
                        piconzero.init()
                        if SHOOTER_ROBOT:
                            piconzero.set_output_config(SHOOTER_MOTOR_CHANNEL, 1)  # set channel 0 to PWM mode
                        if GRIPPER_ROBOT:
                            piconzero.set_output_config(LIFT_SERVO_CHANNEL, 2)
                            piconzero.set_output_config(GRIP_SERVO_CHANNEL, 2)  # set channel 0 and 1 to Servo mode

                        continue
                    elif pack.data == RobotStateData.DISABLE:
                        robot_disabled = True
                        piconzero.cleanup()
                        continue
                    elif pack.data == RobotStateData.E_STOP:
                        piconzero.cleanup()
                        break
            elif pack.type == PacketType.REQUEST:
                # Check for the request type
                if pack.data == RequestData.STATUS:
                    # Send a response
                    fms_sock = socket.socket()  # make a new socket
                    fms_sock.settimeout(.05)

                    try:
                        fms_sock.connect((FMS_IP, PORT))
                        packet = Packet(PacketType.RESPONSE,  # generate a packet saying if the robot is enabled or disabled
                                        RobotStateData.DISABLE if robot_disabled else RobotStateData.ENABLE)

                        fms_sock.send(jsonpickle.encode(packet).encode())  # encode and send

                    except:
                        pass

                    fms_sock.close()
            elif pack.type == PacketType.RESPONSE:
                # do more stuff
                continue
            elif pack.type == PacketType.DATA:
                # See if the robot is disabled
                if robot_disabled:
                    continue

                # Check and see if a list of packets was sent
                if type(pack.data) is list:
                    for item in pack.data:
                        process_data(item)
                else:
                    process_data(pack)

        except Exception as e:
            logger.error(e, exc_info=True)
            pass

    # Emergency Stopped loop
    while True:
        # Disable all outputs
        piconzero.cleanup()

        # Accept a packet
        csock, addr = sock.accept()
        pack = jsonpickle.decode(csock.recv(BUFFER_SIZE).decode())  # receive packets, decode them, then de-json them

        # Check for a request
        if pack.type == PacketType.REQUEST:
            # Send a response, no matter the request type
            fms_sock = socket.socket()  # make a new socket
            fms_sock.settimeout(.2)
            fms_sock.connect((FMS_IP, PORT))
            packet = Packet(PacketType.RESPONSE, RobotStateData.E_STOP)  # generate a packet saying that this robot is e-stopped
            fms_sock.send(jsonpickle.encode(packet).encode())  # encode and send
            fms_sock.close()

        time.sleep(.250)  # delay for 250ms, don't want to spam the picon zero with cleanup requests
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)  # logging level
    main()
