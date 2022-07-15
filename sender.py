import socket
import struct
import binascii
import threading
import time


# alice 10.3.81.2 may change

r_next = 0  # next sequence number to send
size_window = 8  # size of sending window
max_seq = 16  # maximum of sequence number
buffer = {}  # buffer to save packets
send_channel_lock = threading.lock()
r_next_lock = threading.lock()
curr_seq = 0


def parse_pkt(pkt):
    """
    Parse the received packet
    Args:
        pkt: packet received
    Returns:
        seq_num: sequence number
        crc_num: crc number
        data: data contained in the packet
    """
    seq_num = struct.unpack('=I', pkt[0:4])[0]
    crc_num = struct.unpack('=H', pkt[4:6])[0]
    data = pkt[6:].decode('UTF-8', errors='ignore')
    return seq_num, crc_num, data


class Ack(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.socket = socket
        self.start()

    def run(self):
        while True:
            if getattr(self.socket, '_closed'):
                return
            ack_pkt = self.socket.recv(2048)
            seq, ack, next = self.parse(ack_pkt)
            # Lock r_next so that it can not be read when changing
            r_next_lock.acquire()
            prev_r_next = r_next
            r_next = next
            r_next_lock.release()

            if ack != 0:
                send_channel_lock.acquire()
                if seq in buffer.keys():
                    del buffer[seq]
                    for i in range((r_next - prev_r_next) % max_seq):
                        if (prev_r_next + i) % max_seq in buffer.keys():
                            del buffer[(prev_r_next + i) % max_seq]
                send_channel_lock.release()
            else:
                send_channel_lock.acquire()
                buffer[next] = (buffer[next][0], time.time(), 0)
                del buffer[seq]
                self.socket.send(buffer[next][0])
                send_channel_lock.release()


class Sending(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.socket = socket
        self.start()

    def run(self):
        # TODO:
        f = open('/home/VE489task2/shakespeare.txt', 'r')
        first_send = True
        eof = False

        while True:
            r_next_lock.acquire()
            temp_rnext = r_next
            r_next_lock.release()
            if len(buffer) == 0 and eof:
                break
            send_channel_lock.acquire()
            for seq in buffer.keys():
                if buffer[seq][2] == 0 and time.time() - buffer[seq][1] > 3.6:
                    buffer[seq] = (buffer[seq][0], time.time(), 0)
                    self.socket.send(buffer[seq][0])
            send_channel_lock.release()
            if not eof:
                if first_send:
                    for i in range(size_window):
                        send_channel_lock.acquire()
                        seq_num = (curr_seq + i) % max_seq
                        if seq_num not in buffer.keys():
                            data = f.read(1024)
                            if not data:
                                eof = True
                                send_channel_lock.release()
                                break
                            else:
                                packet = struct.pack('=I', seq_num) + struct.pack(
                                    '=H', binascii.crc_hqx(bytes(data, 'UTF-8'), 0)) + bytes(data, 'UTF-8')
                                buffer[seq_num] = (packet, time.time(), 0)
                                self.socket.send(packet)
                        send_channel_lock.release()
                        time.sleep(0.4)
                    first_send = False
                else:
                    for i in range(0, (temp_rnext - curr_seq) % max_seq):
                        send_channel_lock.acquire()
                        seq_num = (curr_seq + i + size_window) % max_seq
                        if seq_num not in buffer.keys():
                            data = f.read(1024)
                            if not data:
                                eof = True
                                send_channel_lock.release()
                                break
                            else:
                                packet = struct.pack('=I', seq_num) + struct.pack(
                                    '=H', binascii.crc_hqx(bytes(data, 'UTF-8'), 0)) + bytes(data, 'UTF-8')
                                buffer[seq_num] = (packet, time.time(), 0)
                                self.socket.send(packet)
                        send_channel_lock.release()
                        time.sleep(0.4)

            curr_seq = temp_rnext
        self.socket.close()
        f.close()


if __name__ == '__main__':
    send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # TODO add rec IP address
    rec_eth = "10.3.94.2"
    send_socket.connect((rec_eth, 10000))

    sending_thread = Sending(send_socket)
    ack_thread = Ack(send_socket)
    sending_thread.join()
    ack_thread.join()
