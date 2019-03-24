import threading
import socket
import select
from core.network.utils import get_ip
from core.network.constants import *

exitFlag = 0
recv_lock = threading.Lock()


class NetworkManager(threading.Thread):
    def __init__(self, logger):
        threading.Thread.__init__(self)
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

    def run(self):
        self.csock, self.fms_addr = self.sock.accept()
        while self.keep_running:
            if select.select((self.csock,), (), (), 0):
                pack = self.csock.recv(BUFFER_SIZE).decode()
                self.logger.info("Recv'd packet")
                recv_lock.acquire()
                self.recv_packet_queue.append(pack)
                recv_lock.release()
        self.csock.close()
                
    def get_next_packet(self):
        return_val = None
        recv_lock.acquire()
        if self.recv_packet_queue:
            return_val = self.recv_packet_queue.pop(0)
        recv_lock.release()
        return return_val

    def stop(self):
        self.keep_running = False

    def send_packet(self, pack):
        # If we have successfully opened a connection to the fms
        if self.csock:
            try:
                self.csock.send(pack.encode())
            except Exception as e:
                pass

