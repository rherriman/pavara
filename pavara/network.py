import sys
#import direct.directbase.DirectStart
from panda3d.core import *
from pandac.PandaModules import *
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
#from pandac.PandaModules import NetDatagram
#from direct.gui.DirectGui import *
import random

from pavara.world import Hector

class Player (object):
    def __init__(self, pid, hector):
        self.pid = pid
        self.hector = hector

    def __repr__(self):
        return 'Player %s' % self.pid

    def handle_command(self, direction, pressed):
        print 'PLAYER %s GOT CMD %s %s' % (self.pid, direction, pressed)
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
        taskMgr.doMethodLater(1.0 / 20.0, self.server_task, 'serverManagementTask')

    def server_task(self, task):
        while self.reader.dataAvailable():
            datagram = NetDatagram()
            if self.reader.getData(datagram):
                addr = datagram.getAddress()
                key = '%s:%s' % (addr.getIpString(), addr.getPort())
                print 'SERVER GOT DATA', key
                if key not in self.players:
                    self.last_pid += 1
                    self.players[key] = Player(self.last_pid, self.world.create_hector())
                dataIter = PyDatagramIterator(datagram)
                player = self.players[key]
                player.handle_command(dataIter.getString(), dataIter.getBool())
        update = PyDatagram()
        update.addInt8(len([o for o in self.world.updatables if o.moved]))
        for obj in self.world.updatables:
            obj.add_update(update)
        for key, player in self.players.iteritems():
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
        taskMgr.add(self.update, 'clientUpdatesFromServer')

    def send(self, cmd, onoff):
        print 'CLIENT SEND', cmd, onoff
        datagram = PyDatagram()
        datagram.addString(cmd)
        datagram.addBool(onoff)
        self.writer.send(datagram, self.connection, self.address)

    def update(self, task):
        while self.reader.dataAvailable():
            datagram = NetDatagram()
            if self.reader.getData(datagram):
                update = PyDatagramIterator(datagram)
                num_objects = update.getInt8()
                for i in range(num_objects):
                    name = update.getString()
                    x = update.getFloat32()
                    y = update.getFloat32()
                    z = update.getFloat32()
                    h = update.getFloat32()
                    p = update.getFloat32()
                    r = update.getFloat32()
                    if name.startswith('Hector') and name not in self.world.objects:
                        self.world.create_hector(name)
                    obj = self.world.objects.get(name)
                    if obj:
                        obj.move((x, y, z))
                        obj.rotate(h, p, r)
        return task.cont
