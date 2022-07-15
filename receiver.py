import socket
import struct
import binascii


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


def check_crc(crc_num, data):
    """
    check whether crc is correct
    Args:
        crc_num: crc unmber to be checked
        data: parsed data
    Returns:
        bool: whether crc number is correct
    """
    return binascii.crc_hqx(bytes(data, 'UTF-8'), 0) == crc_num


def seq_in_range(r_next, size_window, max_seq, seq):
    """
    check whether sequence number is in right range
    Args:
        r_next: next packet to receive
        size_window: size of receiving window
        max_seq: maximum of sequence number
        seq: sequence number of the packet

    Returns:
        bool: whether sequence number is in right range
    """
    if (r_next + size_window - 1) % max_seq > r_next:
        if seq >= r_next and seq <= seq < (r_next + size_window - 1) % max_seq:
            return True
        else:
            return False
    elif (r_next + size_window - 1) % max_seq < r_next:
        if seq < r_next and seq > (r_next + size_window - 1) % max_seq:
            return False
        else:
            return True


def prepare_ack_pkt(seq_num, ack_or_not, r_next):
    """
    prepare ack packet to respond
    Args:
        seq_num: the sequence number that the packet is responding
        ack_or_not: whether receiver ack the packet
    Returns:
        packet: the return packet
    """
    return struct.pack('=I', seq_num) + struct.pack('=H', ack_or_not) + struct.pack('=I', r_next)


def receiver():
    r_next = 0  # next sequence number to receive
    buffer = {}  # buffer to save packets
    receive_data = []  # concat all data in right order
    size_window = 8  # size of receiving window
    max_seq = 16  # maximum of sequence number
    nack = False  # whether it's nack or not
    rec_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # here we choose a arbitrary port 10000

    # TODO: IP address
    rec_socket.bind(("10.3.81.2", 10000))
    rec_socket.listen(1)
    send_socket, send_addr = socket.accept()

    # main process of the receiver
    while True:
        try:
            send_socket.settimeout(10)
            send_pkt = send_socket.recv(2048)
            send_socket.settimeout(None)
            seq, crc, data = parse_pkt(send_pkt)

            # check crc
            crc_true = check_crc(crc, data)
            if crc_true:
                if seq_in_range(r_next, size_window, max_seq, seq):
                    if seq == r_next:
                        receive_data.append(data)
                        next = (r_next + 1) % max_seq
                        for i in range(size_window - 1):
                            num = (r_next + i + 1) % max_seq
                            if num not in buffer.keys():
                                break
                            else:
                                receive_data.append(buffer[num])
                                next = (next + 1) % max_seq
                                del buffer[num]
                        r_next = next
                        nack = False
                        ack_pkt = prepare_ack_pkt(seq, 1, r_next)
                        send_socket.send(ack_pkt)
                    else:
                        if seq not in buffer:
                            buffer[seq] = data
                        if not nack:
                            nack = True
                            ack_pkt = prepare_ack_pkt(seq, 0, r_next)
                        else:
                            ack_pkt = prepare_ack_pkt(seq, 1, r_next)
                        send_socket.send(ack_pkt)
                # else:
                #     # TODO: not in range
                #     ack_pkt = prepare_ack_pkt(seq, 1, r_next)
                #     send_socket.send(ack_pkt)
        except ConnectionResetError:
            break
        except socket.timeout:
            break

    # write data received into a local file
    filename = '/home/yijie/Desktop/receive.txt'
    with open(filename, 'w') as f:
        for data in receive_data:
            f.write(data)
    socket.close()
    return


if __name__ == '__main__':
    receiver()
