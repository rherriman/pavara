import sys, random
from panda3d.core import *
from pandac.PandaModules import WindowProperties
from direct.gui.DirectGui import *
from direct.showbase import Audio3DManager
from direct.showbase.ShowBase import ShowBase
from direct.filter.CommonFilters import CommonFilters

from pavara.maps import load_maps
from pavara.network import Server, Client
from pavara.constants import TCP_PORT
from pavara.world import Block, FreeSolid
from pavara.hector import Hector


class Pavara (ShowBase):
    def __init__(self, *args):
        ShowBase.__init__(self)

        print args

        self.x = None
        self.y = None
        self.filters = CommonFilters(self.win, self.cam)
        self.render.setShaderAuto()
        self.initP3D()
        self.audio3d = Audio3DManager.Audio3DManager(self.sfxManagerList[0], self.cam)
        maps = load_maps('Maps/bodhi.xml', self.cam, audio3d=self.audio3d)
        for map in maps:
            print map.name, '--', map.author
        self.map = maps[0]

        # Testing physical hector.
        """
        incarn = self.map.world.get_incarn()
        hector_color_dict = {
            "barrel_color": [.7,.7,.7],
            "visor_color": [2.0/255, 94.0/255, 115.0/255],
            "body_primary_color": [3.0/255, 127.0/255, 140.0/255],
            "body_secondary_color": [217.0/255, 213.0/255, 154.0/255]
        }
        self.hector = self.map.world.attach(Hector(incarn, colordict=hector_color_dict))
        """

        self.map.show(self.render)
        #taskMgr.add(self.map.world.update, 'worldUpdateTask')

        # axes = loader.loadModel('models/yup-axis')
        # axes.setScale(10)
        # axes.reparentTo(render)

        host = args[0] if args else 'localhost'
        print 'CONNECTING TO', host
        self.client = Client(self.map.world, host, TCP_PORT)

        self.setupInput()

    def initP3D(self):
        self.setBackgroundColor(0, 0, 0)
        self.disableMouse()
        render.setAntialias(AntialiasAttrib.MAuto)
        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)
        self.camera.setPos(0, 20, 40)
        self.camera.setHpr(0, 0, 0)
        self.floater = NodePath(PandaNode("floater"))
        self.floater.reparentTo(render)
        self.up = Vec3(0, 1, 0)
        taskMgr.add(self.move, 'move')

    def setKey(self, key, value):
        self.keyMap[key] = value

    def drop_blocks(self):
        block = self.map.world.attach(FreeSolid(Block((1, 1, 1), (1, 0, 0, 1), 0.01, (0, 40, 0), (0, 0, 0)), 0.01))
        for i in range(10):
            rand_pos = (random.randint(-25, 25), 40, random.randint(-25, 25))
            block = self.map.world.attach(FreeSolid(Block((1, 1, 1), (1, 0, 0, 1), 0.01, rand_pos, (0, 0, 0)), 0.01))

    def exit(self):
#        print self.client.flux.buffer
        sys.exit()

    def setupInput(self):
        self.keyMap = { 'left': 0
                      , 'right': 0
                      , 'forward': 0
                      , 'backward': 0
                      , 'rotateLeft': 0
                      , 'rotateRight': 0
                      , 'walkForward': 0
                      , 'crouch': 0
                      , 'fire': 0
                      , 'missile': 0
                      }
        self.accept('escape', self.exit)
        self.accept('p', self.drop_blocks)
        self.accept('w', self.setKey, ['forward', 1])
        self.accept('w-up', self.setKey, ['forward', 0])
        self.accept('a', self.setKey, ['left', 1])
        self.accept('a-up', self.setKey, ['left', 0])
        self.accept('s', self.setKey, ['backward', 1])
        self.accept('s-up', self.setKey, ['backward', 0])
        self.accept('d', self.setKey, ['right', 1])
        self.accept('d-up', self.setKey, ['right', 0])
        # Hector movement.
        self.accept('i',        self.client.handle_command, ['forward', True])
        self.accept('i-up',     self.client.handle_command, ['forward', False])
        self.accept('j',        self.client.handle_command, ['left', True])
        self.accept('j-up',     self.client.handle_command, ['left', False])
        self.accept('k',        self.client.handle_command, ['backward', True])
        self.accept('k-up',     self.client.handle_command, ['backward', False])
        self.accept('l',        self.client.handle_command, ['right', True])
        self.accept('l-up',     self.client.handle_command, ['right', False])
        self.accept('shift',    self.client.handle_command, ['crouch', True])
        self.accept('shift-up', self.client.handle_command, ['crouch', False])
        self.accept('mouse1',   self.client.handle_command, ['fire', True])
        self.accept('mouse1-up',self.client.handle_command, ['fire', False])
        self.accept('u',        self.client.handle_command, ['missile', True])
        self.accept('u-up',     self.client.handle_command, ['missile', False])

    def move(self, task):
        dt = globalClock.getDt()
        if self.mouseWatcherNode.hasMouse():
            oldx = self.x
            oldy = self.y
            md = self.win.getPointer(0)
            self.x = md.getX()
            self.y = md.getY()
            centerx = self.win.getProperties().getXSize()/2
            centery = self.win.getProperties().getYSize()/2
            self.win.movePointer(0, centerx, centery)

            if (oldx is not None):
                self.floater.setPos(self.camera, 0, 0, 0)
                self.floater.setHpr(self.camera, 0, 0, 0)
                self.floater.setH(self.floater, (centerx-self.x) * 10 * dt)
                p = self.floater.getP()
                self.floater.setP(self.floater, (centery-self.y) * 10 * dt)
                self.floater.setZ(self.floater, -1)
                angle = self.up.angleDeg(self.floater.getPos() - self.camera.getPos())
                if 10 > angle or angle > 170:
                    self.floater.setPos(self.camera, 0, 0, 0)
                    self.floater.setP(p)
                    self.floater.setZ(self.floater, -1)
                self.camera.lookAt(self.floater.getPos(), self.up)
        else:
            self.x = None
            self.y = None
        if (self.keyMap['forward']):
            self.camera.setZ(self.camera, -25 * dt)
        if (self.keyMap['backward']):
            self.camera.setZ(self.camera, 25 * dt)
        if (self.keyMap['left']):
            self.camera.setX(self.camera, -25 * dt)
        if (self.keyMap['right']):
            self.camera.setX(base.camera, 25 * dt)

        return task.cont

if __name__ == '__main__':
    loadPrcFile('pavara.prc')
    p = Pavara(*sys.argv[1:])
    p.run()
