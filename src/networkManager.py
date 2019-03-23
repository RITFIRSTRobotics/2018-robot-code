import threading
import time
import socket
from core.network.utils import get_ip
from core.network.constants import *

exitFlag = 0

class NetworkManager(threading.Thread):
    def __init__(self, logger):
        self.logger = logger
        self.logger.info("opening socket")
        self.sock = socket.socket()
        self.ip_addr = get_ip('wlan0')
        self.logger.info("using ip: `" + self.ip_addr + "`")
        self.sock.bind((self.ip_addr, PORT))
        self.sock.listen(2)
        self.recv_packet_queue = []
        self.keep_running = True
        self.csock = None
        self.fms_addr = None

    def run():
        self.csock, self.fms_addr = sock.accpet()
        while self.keep_running:
            if select.select((self.csock),(),(), 0):
                pack = self.csock.recv(BUFFER_SIZE).decode()
                recv_lock.acquire()
                self.recv_packet_queue.append(pack)
                recv_lock.release()
        self.csock.close()
                
    def get_next_packet():
        retVal = None
        recv_lock.acquire()
        if self.recv_packet_queue:
            retVal = self.recv_packet_queue.pop(0)
        recv_lock.release()
        return retVal

    def stop():
        self.keep_running = False

    def send_packet(pack):
        # If we have successfully opened a connection to the fms
        if self.csock:
            self.csock.send(pack.encode())

