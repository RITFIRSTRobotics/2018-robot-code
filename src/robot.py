import sys
import socket

from core.network.Packet import Packet
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
    # initialize i2c and picon zero

    while True:
        try:
            # Open the socket
            sock = socket.socket()

            # Connect to the FMS
            sock.connect((FMS_IP, PORT))

            # Send a request packet
            packet = Packet(Packet.StorageType.REQUEST, REQUEST_STR)
            size = sock.send(packet)

            # See if an error has occurred
            if size == 0:
                print("main(): error sending packer", file=sys.stderr)
                continue

            # Get a response
            data_pack = sock.recv(BUFFER_SIZE)
            process(data_pack)

        except():
            # do something
            pass

    pass


main()
