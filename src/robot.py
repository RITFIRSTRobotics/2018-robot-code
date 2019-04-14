import os
import sys
import time
import logging
from json import JSONDecodeError
from shutil import copyfile

import jsonpickle
from logging.handlers import RotatingFileHandler

sys.path.append(os.getcwd())  # have to add this for local files
from src.Watchdog import Watchdog
import libs.piconzero as piconzero
from core.network.Packet import Packet, PacketType
from core.network.constants import *
from core.network.packetdata import MovementData
from core.network.packetdata.RequestData import RequestData
from core.network.packetdata.RobotStateData import RobotStateData
from networkManager import NetworkManager

robot_type = str()
m_settings = dict()
d_settings = dict()
state = None


class GripperState:
    """
    Class used to store the current state of the manipulator if it is a gripper
    """
    def __init__(self, lift_servo_min, grip_servo_min):
        self.grip_servo_prev = False
        self.grip_servo_pos = grip_servo_min
        self.lift_servo_pos = lift_servo_min


def is_gripper():
    return robot_type[:-1] == "gripper"


def is_elevator():
    return robot_type == "elevator"


def square_scale(x):
    return int(((x / 128)**2) * (128 if x > 0 else -128))


def process_data(pack):
    """
    Process a packet's data

    :param pack: a packet with data in it
    """
    global state

    # See if the data is MovementData
    if type(pack.data) is MovementData.MovementData:
        # bindings for old code
        pack.data.scale()
        s_side, s_forw = pack.data.get_stick0()

        # Apply drive settings
        s_forw_t = s_forw * d_settings["forward_mod"]
        s_forw = square_scale(s_forw_t) if d_settings["square_forward"] else s_forw_t
        s_side_t = s_side * d_settings["turn_mod"]
        s_side = square_scale(s_side_t) if d_settings["square_turn"] else s_side_t

        # Calculate motor outputs
        if abs(s_forw) < CONTROLLER_DEADZONE and abs(s_side) < CONTROLLER_DEADZONE:
            # First, check deadzones
            left_motor = 0
            right_motor = 0
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

        # See if this is a shooter robot (experimental)
        if is_elevator():
            if pack.data.butttons[2]:
                piconzero.set_output(m_settings["motor_channel"], m_settings["motor_speed"])
            else:
                piconzero.set_output(m_settings["motor_channel"], 0)

        # See if this is a gripper robot
        if is_gripper():
            toggle_button = pack.data.buttons[2]

            # See if the gripper needs to change
            if toggle_button is not state.grip_servo_prev and toggle_button is True:
                if state.grip_servo_pos == m_settings["grip_min"]:
                    grip_servo_pos = m_settings["grip_max"]
                else:
                    grip_servo_pos = m_settings["grip_min"]
                piconzero.set_output(m_settings["grip_servo"], grip_servo_pos)

            # Now for the lift servo
            lift_servo_max = m_settings["lift_min"] + m_settings["lift_range"]
            state.lift_servo_pos += int(pack.data.sticks[2] / m_settings["lift_mod"])
            if state.lift_servo_pos > lift_servo_max or state.lift_servo_pos < lift_servo_max:
                if state.lift_servo_pos > lift_servo_max:
                    state.lift_servo_pos = lift_servo_max
                else:
                    state.lift_servo_pos = m_settings["lift_min"]

            piconzero.set_output(m_settings["lift_servo"], state.lift_servo_pos)
            state.grip_servo_prev = toggle_button  # save for later


def setup_piconzero():
    piconzero.init()

    if is_elevator():
        # set channel 0 to PWM mode
        piconzero.set_output_config(m_settings["motor_channel"], 1)
    if is_gripper():
         # set channel 0 and 1 to Servo mode
        piconzero.set_output_config(m_settings["lift_servo"], 2)
        piconzero.set_output(m_settings["lift_servo"], m_settings["lift_min"])
        piconzero.set_output_config(m_settings["grip_servo"], 2)
        piconzero.set_output(m_settings["grip_servo"], m_settings["grip_min"])


def main():
    # start the logger
    logger = logging.getLogger(__name__)
    handler = RotatingFileHandler('robot_log.log', "a", maxBytes=960000, backupCount=5)
    logger.addHandler(handler)

    # check for a default config file
    if os.path.isfile("settings.default.json") and not os.path.isfile("settings.json"):
        open("settings.json", "a").close()
        copyfile("settings.default.json", "settings.json")

    # read the file
    with open("settings.json", "r") as f:
        values = jsonpickle.loads(f.read())

    # get the results and save them
    global robot_type, m_settings, d_settings, state
    robot_type = values["type"]
    m_settings = values[robot_type]
    d_settings = values["drive"]

    # setup the state object
    if is_gripper():
        state = GripperState(m_settings["lift_min"], m_settings["grip_min"])

    # initalize i2c and piconzero
    setup_piconzero()

    # Open the socket and start the listener thread
    netwk_mgr = NetworkManager(logger)
    netwk_mgr.start()

    # Make robot stuff
    robot_disabled = True
    watchdog = Watchdog(logger)

    # Initialization should be done now, start accepting packets
    while True:
        try:
            if netwk_mgr.get_rerun_setup():
                setup_piconzero()
            raw_pack = netwk_mgr.get_next_packet()
            if raw_pack is not None and raw_pack != "":
                try:
                    pack = jsonpickle.decode(raw_pack)  # recieve packets, decode them, then de-json them
                except JSONDecodeError as e:
                    print(e)
                    print(raw_pack)
                    logger.warning(str(e))
                    continue
                watchdog.reset()

                # Type-check the data
                if type(pack) is not Packet:
                    print(type(pack))
                    print("pack is not a Packet", file=sys.stderr)
                    continue

                # Process the packet
                if pack.type == PacketType.STATUS:
                    # Check the contents of the packet
                    if type(pack.data) is RobotStateData:
                        if pack.data == RobotStateData.ENABLE:
                            robot_disabled = False

                        # Reinitialize the picon zero
                        setup_piconzero()
                        continue
                        
                    elif pack.data == RobotStateData.DISABLE:
                        robot_disabled = True
                        piconzero.cleanup()
                        continue

                    elif pack.data == RobotStateData.E_STOP:
                        piconzero.cleanup()
                        break
                        
                elif pack.type == PacketType.REQUEST:
                    print("Got request packet")
                    # Check for the request type
                    if pack.data == RequestData.STATUS:
                        # Send a response
                        packet = Packet(PacketType.RESPONSE,  # generate a packet saying if the robot is enabled or disabled
                                        RobotStateData.DISABLE if robot_disabled else RobotStateData.ENABLE)

                        netwk_mgr.send_packet(jsonpickle.encode(packet))

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
        raw_pack = netwk_mgr.get_next_packet()
        if raw_pack is not None:
            pack = jsonpickle.decode(raw_pack)  # receive packets, decode them, then de-json them

            # Check for a request
            if pack.type == PacketType.REQUEST:
                # Send a response, no matter the request type
                packet = Packet(PacketType.RESPONSE, RobotStateData.E_STOP)  # generate a packet saying that this robot is e-stopped
                netwk_mgr.send_packet(packet)

            time.sleep(.250)  # delay for 250ms, don't want to spam the picon zero with cleanup requests
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)  # logging level
    main()
