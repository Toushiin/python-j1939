from __future__ import print_function
import j1939

#
# for responding to seed/key requests provide your own keyGenerator
# class..
# mine is returned in a SeedToKey meghod of a Genkey class that sits elsewhere
# on my PYTHONPATH and is propriatiry
#
# TODO: use a better baseclass override model.
#
try:
    import genkey
    security = genkey.GenKey()
    print("Private Genkey Loaded")
except:
    # Stuff in a fake genKey responder.  Pretty much just needs a
    # reference to any class that can convert a Seed to a Key..  For
    # obvious reasons I'm not posting mine
    print("Genkey Not loaded, This one will generate garbage keys")
    class Genkey:
        def SeedToKey(self, seed):
            return 0x12345678

    security = Genkey()

def set_mem_object_single(channel='can0', bustype='socketcan', length=4, src=0, dest=0x17, pointer=0, extension=0, value=0):
    #from can.interfaces.interface import *

    countdown = 10
    result = -1

    bus = j1939.Bus(channel=channel, bustype=bustype, timeout=0.01, keygen=security.SeedToKey, broadcast=False)
    node = j1939.Node(bus, j1939.NodeName(), [src])
    bus.connect(node)

    #dm14pgn = j1939.PGN()
    dm14data = [length, 0x15, pointer, 0x00, 0x00, extension, 0xff, 0xff]

    dm14pgn = j1939.PGN(pdu_format=0xd9, pdu_specific=dest)
    #dm14pgn = j1939.PGN().value = 0xd917
    #print ("dm14pgn=", dm14pgn)
    #print ("dm14pgn.destination_address_value=", dm14pgn.destination_address_value)
    #print ("dm14pgn.pdu_specific=", dm14pgn.pdu_specific)
    dm14aid = j1939.ArbitrationID(pgn=dm14pgn, source_address=src, destination_address=dest)
    dm14pdu = j1939.PDU(timestamp=0.0, arbitration_id=dm14aid, data=dm14data, info_strings=None)
    dm14pdu.display_radix='hex'


    bus.send(dm14pdu)

    sendBuffer = []
    sendBuffer.append(length)
    for i in range(0, length):
        sendBuffer.append(0)

    #sendBuffer = [length, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]

    print("## length=%d, value=%s " % (length, value))
    if isinstance(value, int):
        if length == 1:
            sendBuffer[1] = value
        elif length == 2:
            sendBuffer[1] = value & 0xff
            sendBuffer[2] = (value >> 8) & 0xff
        elif length == 3:
            sendBuffer[1] = value & 0xff
            sendBuffer[2] = (value >> 8) & 0xff
            sendBuffer[3] = (value >> 16) & 0xff
        elif length == 4:
            sendBuffer[1] = value & 0xff
            sendBuffer[2] = (value >> 8) & 0xff
            sendBuffer[3] = (value >> 16) & 0xff
            sendBuffer[4] = (value >> 24) & 0xff
        else:
            raise ValueError("Don't know how to send a %d byte integer" % length)

    elif isinstance(value, list):
        for i in range(len(value)):
            sendBuffer[i+1] = value[i]

    elif isinstance(value, str):
        sendBuffer[0] = length+1
        for i in range(len(value)):
            sendBuffer[i+1] = ord(value[i])

    print("## sendBuffer=%s " % (sendBuffer))

    dm16pgn = j1939.PGN(pdu_format=0xd7, pdu_specific=dest)
    dm16aid = j1939.ArbitrationID(pgn=dm16pgn, source_address=src, destination_address=dest)
    dm16pdu = j1939.PDU(timestamp=0.0, arbitration_id=dm16aid, data=sendBuffer)
    dm16pdu.display_radix='hex'

    print("## PDU=%s " % (dm16pdu))

    # Wait around for a while looking for the second proceed

    countdown=10
    proceedCount = 0
    while countdown:
        countdown -= 1
        rcvPdu = bus.recv(2)
        if rcvPdu:
            rcvPdu.display_radix='hex'
            print("received PDU: %s", rcvPdu)
            if rcvPdu.pgn == 0xd800:
                if rcvPdu.data[0]==1 and rcvPdu.data[1]==0x11:
                    proceedCount += 1
                    if proceedCount == 2:
                        bus.send(dm16pdu)
                        print('Sent ', dm16pdu)
                if rcvPdu.data[0]==0 and rcvPdu.data[1]==0x19:
                    print("Value Sent")
                    break


    bus.shutdown()

    return result




def get_mem_object_single(channel='can0', bustype='socketcan', length=4, src=0, dest=0x17, pointer=0, extension=0):
    #from can.interfaces.interface import *

    countdown = 10
    result = None

    bus = j1939.Bus(channel=channel, bustype=bustype, timeout=0.01, broadcast=False)
    node = j1939.Node(bus, j1939.NodeName(), [src])
    bus.connect(node)
    pgn = j1939.PGN()
    pgn.value = 0xd900 + dest # Request a DM14 mem-object
    aid = j1939.ArbitrationID(pgn=pgn, source_address=src, destination_address=dest)

    data = [length, 0x13, pointer, 0x00, 0x00, extension, 0xff, 0xff]
    pdu = j1939.PDU(timestamp=0.0, arbitration_id=aid, data=data, info_strings=None)
    assert(pdu != None)
    pdu.display_radix='hex'
    bus.send(pdu)
    while countdown:
        pdu = bus.recv(timeout=1)
        if pdu is None:
            continue
        print(pdu)
        if pdu.pgn == 0xd700:
            value = list(pdu.data)
            length = value[0]
            if length == 1:
                result = value[1]
            elif length == 2:
                result = (value[2] << 8) + value[1]
            elif length == 4:
                result = (value[4] << 24) + (value[3] << 16) + (value[2] << 8) + value[1]
            else:
                result = value[1:]
            break # got what I was waiting for
        countdown -= 1
    bus.shutdown()
    if result is None:
        raise IOError(" no CAN response")
    return result

def request_pgn_single(requested_pgn, channel='can0', bustype='socketcan', length=4, src=0, dest=0x17):

    countdown = 10
    result = None

    if not isinstance(requested_pgn, int):
        raise ValueError("pgn must be an integer.")

    bus = j1939.Bus(channel=channel, bustype=bustype, timeout=0.01)
    pgn = j1939.PGN()
    pgn.value = 0xea00 + dest # request_pgn mem-object
    aid = j1939.ArbitrationID(pgn=pgn, source_address=src, destination_address=dest)

    pgn0 = requested_pgn & 0xff
    pgn1 = (requested_pgn >> 8) & 0xff
    pgn2 = (requested_pgn >> 16) & 0xff

    data = [pgn0, pgn1, pgn2]
    pdu = j1939.PDU(timestamp=0.0, arbitration_id=aid, data=data, info_strings=None)

    pdu.display_radix='hex'

    bus.send(pdu)

    while countdown:
        pdu = bus.recv(timeout=1)
        if pdu and (pdu.pgn == 0xe800 or pdu.pgn == requested_pgn):
            result = list(pdu.data) 
            break # got what I was waiting for

        if pdu: 
            countdown -= 1

    bus.shutdown()

    if not result:
        raise IOError(" no CAN response")


    return result


def send_pgn(requested_pgn, data, channel='can0', bustype='socketcan', length=4, src=0, dest=0x17, bus=None):

    countdown = 10
    result = None

    if not isinstance(requested_pgn, int):
        raise ValueError("pgn must be an integer.")
    if bus is None:
        bus = j1939.Bus(channel=channel, bustype=bustype, timeout=0.01, keygen=security.SeedToKey)
        close = True
    else:
        close = False
    pgn = j1939.PGN()
    if requested_pgn < 0xf000:
        requested_pgn |= dest
    pgn.value = requested_pgn#0xea00 + dest # request_pgn mem-object
    aid = j1939.ArbitrationID(pgn=pgn, source_address=src, destination_address=dest)

    print(data)
    pdu = j1939.PDU(timestamp=0.0, arbitration_id=aid, data=data, info_strings=None)

    pdu.display_radix='hex'

    bus.send(pdu)
    if close:
        bus.shutdown()
    if 0:
        while countdown:
            pdu = bus.recv(timeout=1)
            if pdu and (pdu.pgn == 0xe800 or pdu.pgn == requested_pgn):
                result = list(pdu.data) 
                break # got what I was waiting for

            if pdu: 
                countdown -= 1


        if not result:
            raise IOError(" no CAN response")


        return result

