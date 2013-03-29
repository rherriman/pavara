import sys
from panda3d.core import *
from direct.gui.DirectGui import *
from direct.showbase import Audio3DManager
from direct.showbase.ShowBase import ShowBase

from pavara.maps import load_maps
from pavara.network import Server
from pavara.constants import TCP_PORT

class PavaraServer (ShowBase):
    def __init__(self, *args):
        ShowBase.__init__(self)
        self.audio3d = Audio3DManager.Audio3DManager(self.sfxManagerList[0], self.cam)
        maps = load_maps('Maps/bodhi.xml', self.cam, audio3d=self.audio3d)
        self.map = maps[0]
        self.map.show(self.render)
        taskMgr.add(self.map.world.update, 'worldUpdateTask')
        self.server = Server(self.map.world, TCP_PORT)

if __name__ == '__main__':
    loadPrcFile('server.prc')
    p = PavaraServer(*sys.argv[1:])
    p.run()
