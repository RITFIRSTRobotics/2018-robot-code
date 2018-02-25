import os
import sys
import time
import socket
import logging
import jsonpickle
from logging.handlers import RotatingFileHandler

sys.path.append(os.getcwd())
from core.network.Packet import Packet, PacketType
from core.network.constants import *
from core.network.packetdata import MovementData

import libs.piconzero as piconzero
from core.network.packetdata.RequestData import RequestData
from core.network.packetdata.RobotStateData import RobotStateData


def process_data(pack):
    """
    Process a packet's data

    :param pack: a packet with data in it
    """

    # See if the data is MovementData
    if type(pack.data) is MovementData:
        # move robot
        pack.data.scale()

        # bindings for old code
        s_forw = pack.data.stick_y
        s_side = pack.data.stick_x

        # Calculate motor outputs
        if pack.data.stick_x < CONTROLLER_DEADZONE and pack.data.stick_y < CONTROLLER_DEADZONE:
            # First, check deadzones
            left_motor = 0
            right_motor = 0
        elif s_forw > 0:
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
                right_motor = -1 * max(-s_forw, -s_side)

        # Range check
        if left_motor > 0:
            left_motor = min(left_motor, 127)
        else:
            left_motor = max(left_motor, -128)
        if right_motor > 0:
            right_motor = min(right_motor, 127)
        else:
            right_motor = max(right_motor, -128)

        piconzero.set_motor(piconzero.MOTORA, left_motor)
        piconzero.set_motor(piconzero.MOTORB, right_motor)


def main():
    # start the logger
    logger = logging.getLogger(__name__)
    handler = RotatingFileHandler('robot_log.log', "a", maxBytes=960000, backupCount=5)
    logger.addHandler(handler)

    # initialize i2c and picon zero
    piconzero.init()

    # Open the socket
    logger.info("opening socket")
    sock = socket.socket()

    # Figure out and log the ip of the robot
#    ip = socket.gethostbyname(socket.gethostname())
    ip = "10.0.1.10"
    logger.info("using ip: `" + ip + "`")
    sock.bind((ip, PORT))  # bind it to the socket
    sock.listen(5)  # listen for incoming data

    robot_disabled = True

    # Initialization should be done now, start accepting packets
    while True:
        try:
            # Get a connection
            csock, addr = sock.accept()

            # Accept a packet
            pack = jsonpickle.decode(csock.recv(BUFFER_SIZE).decode())  # recieve packets, decode them, then de-json them

            print(pack.data)

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
                        continue
                    elif pack.data == RobotStateData.DISABLE:
                        robot_disabled = True
                        continue
                    elif pack.data == RobotStateData.E_STOP:
                        break
            elif pack.type == PacketType.REQUEST:
                # Check for the request type
                if pack.data == RequestData.STATUS:
                    # Send a response
                    fms_sock = socket.socket()  # make a new socket
                    fms_sock.connect((FMS_IP, PORT))
                    packet = Packet(PacketType.RESPONSE,  # generate a packet saying if the robot is enabled or disabled
                                    RobotStateData.DISABLE if robot_disabled else RobotStateData.ENABLE)
                    fms_sock.send(jsonpickle.encode(packet).encode())  # encode and send
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
        pack = jsonpickle.decode(sock.recv(BUFFER_SIZE).decode())  # receive packets, decode them, then de-json them

        # Check for a request
        if pack.type == PacketType.REQUEST:
            # Send a response, no matter the request type
            fms_sock = socket.socket()  # make a new socket
            fms_sock.connect((FMS_IP, PORT))
            packet = Packet(PacketType.RESPONSE, RobotStateData.E_STOP)  # generate a packet saying that this robot is e-stopped
            fms_sock.send(jsonpickle.encode(packet).encode())  # encode and send
            fms_sock.close()

        time.sleep(.250)  # delay for 250ms, don't want to spam the picon zero with cleanup requests
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)  # logging level
    main()
