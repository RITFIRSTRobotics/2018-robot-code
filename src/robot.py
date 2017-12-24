import sys
import socket
import logging
from logging.handlers import RotatingFileHandler

import jsonpickle as jsonpickle

from core.network.Packet import Packet, StorageType
from core.network.constants import *
from core.network.packetdata import MovementData


def process(pack):
    # Make sure this is a packet
    if (type(pack) is not Packet):
        print("process(pack): pack not a Packet", file=sys.stderr)
        return None

    # Process packet
    if (type(pack.get_data()) is MovementData):
        # move robot
        pass


def main():
    # start the logger
    logger = logging.getLogger(__name__)
    handler = RotatingFileHandler('robot_log.log', "a", maxBytes=960000, backupCount=5)
    logger.addHandler(handler)

    # initialize i2c and picon zero
    """"""

    # Open the socket
    logger.info("opening socket")
    sock = socket.socket()

    # Figure out and log the ip of the robot
    ip = socket.gethostbyname(socket.gethostname())
    logger.info("using ip: `" + ip + "`")
    sock.bind((ip, PORT)) # bind it to the socket
    sock.connect((FMS_IP, PORT))

    # Initialization should be done now, start accepting packets
    while True:
        try:
            # Get a response
            data_pack = sock.recv(BUFFER_SIZE)
            print(data_pack.decode())
            process(data_pack)

        except Exception as e:
            logger.error(e, exc_info=True)
            pass

    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)  # logging level
    main()
