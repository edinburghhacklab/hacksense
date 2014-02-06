import crc16
import socket
import time

SOT = str(unichr(0x01))
STX = str(unichr(0x02))
ETX = str(unichr(0x03))
EOT = str(unichr(0x04))
ENQ = str(unichr(0x05))
ACK = str(unichr(0x06))
SOL = str(unichr(0x0A))
EOC = str(unichr(0x0C))
EOL = str(unichr(0x0D))
SOP = str(unichr(0x0E))
EOP = str(unichr(0x0F))
ESC = str(unichr(0x1B))
SEP = str(unichr(0x1E))

BITMAP_FONT = ESC + '\xA0' + '0'
NORMAL_FONT = ESC + '\xA0' + '1'
LARGE_FONT = ESC + '\xA0' + '2'
SMALL_FONT = ESC + '\xA0' + '3'

BLACK = ESC + '\xA1' + '0'
RED = ESC + '\xA1' + '1'
GREEN = ESC + '\xA1' + '2'
YELLOW = ESC + '\xA1' + '3'

ENABLE_IMMEDIATELY = ESC + '\xA5' + '\x04'

OUTLINE_CENTRE = ESC + '\xA3' + '1'

APPEAR_JUMP = ESC + '\xC0' + '00'
APPEAR_SCROLL = ESC + '\xC0' + '01'
APPEAR_AUTO = ESC + '\xC0' + '02'
APPEAR_VERTICAL = ESC + '\xC0' + '03'

class Rhapsody(object):
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.connect()

    def __del__(self):
        self.socket.close()

    def connect(self):
        self.socket = socket.socket()
        self.socket.connect((self.host, self.port))

    def send_raw(self, packet):
        print "sending packet: %r (len %s)" % (packet, len(packet))
        self.socket.send(packet)
        #sock.close()

    def send(self, packet):
        return self.send_raw(self.transmission(self.extended_udp_packet(packet)))

    def page(self, number, lines):
        return SOP + '%02X' % (number) + ''.join(lines) + 'EOP'

    def line(self, number, data):
        return SOL + '%02X' % (number) + SEP + data + EOL

    def extended_udp_packet(self, innermsg):
        return ENQ + '01FE00' + hex(len(innermsg))[2:].upper().zfill(2) + innermsg
    
    def transmission(self, packet):
        crc = crc16.crc16xmodem(packet)
        return SOT + packet + hex(crc)[2:].upper().zfill(4) + EOT

    def configure_display(self, width, lines):
        output = ESC + '\xE4' + '%02X' % (width)
        for line in lines:
            output = output + '%02X' % (line)
        output = output + EOC
        return output

    def set_time(self, t=None):
        if t is None:
            t = time.localtime()
        return ESC + '\xE6' + time.strftime('%y%m%d%H%M%S', t) + EOC
