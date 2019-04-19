import threading
import socket
import select
from json import JSONDecodeError

import jsonpickle

from core.network.utils import get_ip
from core.network.constants import *
import time

exitFlag = 0


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
        self.recv_lock = threading.Lock()
        self.rerun_setup = False
        self.time_of_last_packet = time.time()
        self.socket_open = False

    def run(self):
        self.csock, self.fms_addr = self.sock.accept()
        self.socket_open = True
        self.time_of_last_packet = time.time()
        while self.keep_running:
            if time.time() - self.time_of_last_packet > TIMEOUT_TIME:
                print ("Attempting reconnect")
                if self.socket_open:
                    self.csock.close()
                    self.socket_open = False
                self.csock, self.fms_addr = self.sock.accept()
                self.socket_open = True
                self.rerun_setup = True
            elif select.select((self.csock,), (), (), 0)[0]:
                with self.recv_lock:
                    pack = self.csock.recv(BUFFER_SIZE).decode()
                    packList = pack.split("}{")
                    if len(packList) > 1:
                        for i in range(len(packList)):
                            if i != 0:
                                packList[i] = "{" + packList[i]
                            if i != len(packList) - 1:
                                packList[i] = packList[i] + "}"
                    self.time_of_last_packet = time.time()
                    self.recv_packet_queue.extend(packList)
            else:
                time.sleep(.05)
        self.csock.close()
        self.sock.close()
                
    def get_next_packet(self):
        ret_val = None
        pack_string = None
        self.recv_lock.acquire()
        if self.recv_packet_queue:
            pack_string = self.recv_packet_queue.pop(0)
            try_again = True
            while try_again:
                try:
                    ret_val = jsonpickle.decode(pack_string)
                    try_again = False
                except JSONDecodeError as e:
                    print("Broken packet")
                    if len(self.recv_packet_queue) > 1:
                        pack_string = pack_string + self.recv_packet_queue.pop(0)
                        try_again = True
                    else:
                        try_again = False
        self.recv_lock.release()
        return ret_val

    def stop(self):
        self.keep_running = False

    def send_packet(self, pack):
        # If we have successfully opened a connection to the fms
        if self.csock:
            try:
                self.csock.send(pack.encode())
            except Exception as e:
                pass

    def get_rerun_setup(self):
        return self.rerun_setup

