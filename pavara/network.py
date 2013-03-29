import sys
#import direct.directbase.DirectStart
from panda3d.core import *
from pandac.PandaModules import *
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
#from pandac.PandaModules import NetDatagram
#from direct.gui.DirectGui import *

MOVEMENT_MASKS = {
    'forward': BitMask32(0x01),
    'backward': BitMask32(0x02),
    'left': BitMask32(0x04),
    'right': BitMask32(0x08),
    'crouch': BitMask32(0x10),
}

FORWARD_MASK = BitMask32(0x01)
BACKWARD_MASK = BitMask32(0x02)
LEFT_MASK = BitMask32(0x04)
RIGHT_MASK = BitMask32(0x08)
CROUCH_MASK = BitMask32(0x10)

class FluxCapacitor (object):
    def __init__(self, size=500):
        self.buffer = []
        for i in range(size):
            self.buffer.append([{}, -1])
        self.oldest = 0
        self.total_buffered = 0

    def find(self, frame):
        offset = self.oldest if self.total_buffered == len(self.buffer) else 0
        start = 0
        end = self.total_buffered - 1

        while start <= end:
            mid = start + ((end - start) / 2)
            adjusted = (mid + offset) % self.total_buffered
            if self.buffer[adjusted][1] == frame:
                return self.buffer[adjusted][0]
            elif self.buffer[adjusted][1] > frame:
                end = mid - 1
            else:
                start = mid + 1
        return {}

    def snapshot(self, frame):
        # Get the oldest object and clear it out (re-using it).
        obj = self.buffer[self.oldest][0]
        obj.clear()
        # Set the current frame, and advance the oldest pointer.
        self.buffer[self.oldest][1] = frame
        self.oldest += 1
        if self.oldest >= len(self.buffer):
            self.oldest = 0
        if self.total_buffered < len(self.buffer):
            self.total_buffered += 1
        return obj

class Player (object):
    def __init__(self, pid, hector):
        self.pid = pid
        self.hector = hector

    def __repr__(self):
        return 'Player %s' % self.pid

    def handle_command(self, direction, pressed):
        self.hector.handle_command(direction, pressed)

class Server (object):
    def __init__(self, world, port):
        self.world = world
        self.manager = QueuedConnectionManager()
        self.reader = QueuedConnectionReader(self.manager, 0)
        self.writer = ConnectionWriter(self.manager, 0)
        self.connection = self.manager.openUDPConnection(port)
        self.reader.addConnection(self.connection)
        self.players = {}
        self.last_pid = 0
        taskMgr.add(self.client_updates, 'updatesFromClients')
        taskMgr.doMethodLater(1.0 / 20.0, self.server_task, 'serverManagementTask')

    def client_updates(self, task):
        while self.reader.dataAvailable():
            datagram = NetDatagram()
            if self.reader.getData(datagram):
                addr = datagram.getAddress()
                key = '%s:%s' % (addr.getIpString(), addr.getPort())
                if key not in self.players:
                    self.last_pid += 1
                    self.players[key] = Player(self.last_pid, self.world.create_hector())
                    start = PyDatagram()
                    start.addUint8(self.last_pid)
                    start.addUint32(self.world.frame)
                    start.addString(self.players[key].hector.name)
                    self.writer.send(start, self.connection, addr)
                dataIter = PyDatagramIterator(datagram)
                player = self.players[key]
                f = dataIter.getUint32()
                movement = BitMask32(dataIter.getUint32())
                for key, mask in MOVEMENT_MASKS.items():
                    on = movement & mask
                    player.handle_command(key, on.get_word() > 0)
        return task.cont

    def server_task(self, task):
        moved_objects = [o for o in self.world.updatables if o.moved]
        # Broadcast the positions of anything that moved, along with the last frame received, to each client.
        for key, player in self.players.iteritems():
            update = PyDatagram()
            update.addUint32(self.world.frame)
            update.addInt8(len(moved_objects))
            for obj in moved_objects:
                obj.add_update(update)
            ip, port = key.split(':', 1)
            addr = NetAddress()
            addr.set_host(ip, int(port))
            self.writer.send(update, self.connection, addr)
        return task.again

class Client (object):
    def __init__(self, world, host, port):
        self.world = world
        self.manager = QueuedConnectionManager()
        self.reader = QueuedConnectionReader(self.manager, 0)
        self.writer = ConnectionWriter(self.manager, 0)
        self.connection = self.manager.openUDPConnection(0)
        self.reader.addConnection(self.connection)
        self.address = NetAddress()
        self.address.set_host(host, port)
        self.players = {}
        self.flux = FluxCapacitor()
        self.hector = None
        self.movement = {
            'forward': False,
            'backward': False,
            'left': False,
            'right': False,
            'crouch': False,
        }
        taskMgr.add(self.update, 'clientUpdatesFromServer')

    def send(self):
        num = BitMask32(0)
        for key, mask in MOVEMENT_MASKS.items():
            if self.movement[key]:
                num |= mask
        datagram = PyDatagram()
        datagram.addUint32(self.world.frame)
        datagram.addUint32(num.get_word())
        self.writer.send(datagram, self.connection, self.address)

    def handle_command(self, cmd, onoff):
        self.movement[cmd] = onoff
        if self.hector:
            self.hector.handle_command(cmd, onoff)

    def handle_updates(self, datagram):
        update = PyDatagramIterator(datagram)
        server_frame = update.getUint32()
        snapshot = self.flux.find(server_frame)
        num_objects = update.getInt8()
        for i in range(num_objects):
            name = update.getString()
            numfloats = update.getUint8()
            floats = [update.getFloat32() for _ in range(numfloats)]
            x = floats[0]
            y = floats[1]
            z = floats[2]
            h = floats[3]
            p = floats[4]
            r = floats[5]
            obj = self.world.objects.get(name)
            if obj:
                new_pos = Point3(x, y, z)
                if snapshot and obj.name in snapshot:
                    old_pos = snapshot[obj.name]
                    d = new_pos - old_pos
                    if d.length() > 0.1:
                        if d.length() > 0.25:
                            qual = 'MAJOR'
                            obj.move((x, y, z))
                        else:
                            qual = 'MINOR'
                            obj.move_by(d.x * 0.5, d.y * 0.5, d.z * 0.5)
                        print '%s CORRECTION [server t=%s] %s :: %s -> %s' % (qual, server_frame, obj, old_pos, new_pos)
                        obj.rotate(h, p, r)
                        if len(floats) == 12:
                            obj.xz_velocity.x = floats[6]
                            obj.xz_velocity.y = floats[7]
                            obj.xz_velocity.z = floats[8]
                            obj.y_velocity.x = floats[9]
                            obj.y_velocity.y = floats[10]
                            obj.y_velocity.z = floats[11]
#                        obj.move((x, y, z))
#                        obj.rotate(h, p, r)

    def update(self, task):
        self.send()
        if self.hector:
            snapshot = self.flux.snapshot(self.world.frame)
            for obj in self.world.predictables:
                snapshot[obj.name] = obj.position()
        while self.reader.dataAvailable():
            datagram = NetDatagram()
            if self.reader.getData(datagram):
                if self.hector:
                    self.handle_updates(datagram)
                else:
                    start = PyDatagramIterator(datagram)
                    pid = start.getUint8()
                    server_frame = start.getUint32()
                    name = start.getString()
                    print 'STARTING CLIENT %s - %s' % (pid, name)
                    self.hector = self.world.create_hector(name)
                    self.world.frame = server_frame
                    taskMgr.add(self.world.update, 'worldUpdateTask')
        return task.cont
