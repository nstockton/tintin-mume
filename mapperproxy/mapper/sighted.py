# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
###Some code borrowed from pymunk's debug drawing functions###

import logging
import pyglet
import os.path
from re import search
pyglet.options['debug_gl'] = False
try:
	from Queue import Empty as QueueEmpty
except ImportError:
	from queue import Empty as QueueEmpty

from .config import Config, config_lock
from .constants import DIRECTIONS, TERRAIN_COLORS
from .utils import iterItems, getDirectoryPath


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')
#logger.setLevel('INFO')

FPS = 40

TILESDIR = getDirectoryPath("tiles")

TILES = {
	# terrain
	"field": pyglet.image.load(os.path.join(TILESDIR, "field.png")),
	"brush": pyglet.image.load(os.path.join(TILESDIR, "brush.png")),
	"forest": pyglet.image.load(os.path.join(TILESDIR, "forest.png")),
	"hills": pyglet.image.load(os.path.join(TILESDIR, "hill.png")),
	"mountains": pyglet.image.load(os.path.join(TILESDIR, "mountain.png")),
	"shallowwater": pyglet.image.load(os.path.join(TILESDIR, "swamp.png")),
	"water": pyglet.image.load(os.path.join(TILESDIR, "water.png")),
	"rapids": pyglet.image.load(os.path.join(TILESDIR, "rapid.png")),
	"underwater": pyglet.image.load(os.path.join(TILESDIR, "underwater.png")),
	"cavern": pyglet.image.load(os.path.join(TILESDIR, "cavern.png")),
	"tunnel": pyglet.image.load(os.path.join(TILESDIR, "tunnel.png")),
	"road": pyglet.image.load(os.path.join(TILESDIR, "road.png")),
	"city": pyglet.image.load(os.path.join(TILESDIR, "city.png")),
	"indoors": pyglet.image.load(os.path.join(TILESDIR, "indoor.png")),
	"random": pyglet.image.load(os.path.join(TILESDIR, "random.png")),
	"undefined": pyglet.image.load(os.path.join(TILESDIR, "undefined.png")),
	"death": pyglet.image.load(os.path.join(TILESDIR, "undefined.png")),
	# exits
	"wallnorth": pyglet.image.load(os.path.join(TILESDIR, "wallnorth.png")),
	"walleast": pyglet.image.load(os.path.join(TILESDIR, "walleast.png")),
	"wallsouth": pyglet.image.load(os.path.join(TILESDIR, "wallsouth.png")),
	"wallwest": pyglet.image.load(os.path.join(TILESDIR, "wallwest.png")), 
	"exitup": pyglet.image.load(os.path.join(TILESDIR, "exitup.png")),
	"exitdown": pyglet.image.load(os.path.join(TILESDIR, "exitdown.png")),
	# load flags
	"attention": pyglet.image.load(os.path.join(TILESDIR, "attention.png")),
	"armour": pyglet.image.load(os.path.join(TILESDIR, "armour.png")),
	"herb": pyglet.image.load(os.path.join(TILESDIR, "herb.png")),
	"key": pyglet.image.load(os.path.join(TILESDIR, "key.png")),
	"treasure": pyglet.image.load(os.path.join(TILESDIR, "treasure.png")),
	"weapon": pyglet.image.load(os.path.join(TILESDIR, "weapon.png")),
	# mob flags
	"guild": pyglet.image.load(os.path.join(TILESDIR, "guild.png")),
	"quest": pyglet.image.load(os.path.join(TILESDIR, "quest.png")),
	"rent": pyglet.image.load(os.path.join(TILESDIR, "rent.png")),
	"shop": pyglet.image.load(os.path.join(TILESDIR, "shop.png")),
	"smob": pyglet.image.load(os.path.join(TILESDIR, "smob.png")),
	# player
	"player": pyglet.image.load(os.path.join(TILESDIR, "player.png"))
}

class Window(pyglet.window.Window):
	def __init__(self, world):

		# mapperproxy world
		self.world = world

		### map variables
		# number of columns
		self.col=9
		# number of rows
		self.row=23
		# the center of the window
		self.mcol = int(self.col/2)
		self.mrow = int(self.row/2)
		self.radius = (self.mcol, self.mrow, 1)
		# the size of a tile in pixel
		self.square=32
		# the list of visible rooms:
		# a dictionary using a tuple of coordinates (x, y) as keys
		self.visibleRooms = {}
		# player position and central rooms
		# they are set to None at startup
		self.playerRoom = None
		self.centerRoom = None

		### pyglet window
		super(Window, self).__init__(
			self.col*self.square, self.row*self.square,
			caption='MPM', resizable=True)
		logger.info("Creating window {}".format(self))
		self._gui_queue = world._gui_queue
		self._gui_queue_lock = world._gui_queue_lock

		### sprites
		# the list of sprites
		self.sprites = []
		# pyglet batch of sprites
		self.batch = pyglet.graphics.Batch()
		# the list of visible layers (level 0 is covered by level 1)
		self.layer = []
		self.layer.append(pyglet.graphics.OrderedGroup(0))
		self.layer.append(pyglet.graphics.OrderedGroup(1))
		self.layer.append(pyglet.graphics.OrderedGroup(2))
		self.layer.append(pyglet.graphics.OrderedGroup(3))

		### Define FPS
		pyglet.clock.schedule_interval_soft(self.queue_observer, 1.0 / FPS)

	def queue_observer(self, dt):
		with self._gui_queue_lock:
			while not self._gui_queue.empty():
				try:
					event = self._gui_queue.get_nowait()
					if event is None:
						event = ("on_close",)
					self.dispatch_event(event[0], *event[1:])
				except QueueEmpty:
					break

	def on_close(self):
		logger.debug("Closing window {}".format(self))
		super(Window, self).on_close()

	def on_draw(self):
		logger.debug("Drawing window {}".format(self))
		# pyglet stuff to clear the window
		self.clear()
		# pyglet stuff to print the batch of sprites
		self.batch.draw()

	def on_resize(self, width, height):
		logger.debug("Resizing window {}".format(self))
		super(Window, self).on_resize(width, height)
		# reset window size
		self.col = int(width/self.square)
		self.mcol = int(self.col/2)
		self.row = int(height/self.square)
		self.mrow = int(self.row/2)
		self.radius = (self.mcol, self.mrow, 1)
		if self.centerRoom is not None:
			self.draw_map(self.centerRoom)

	def on_map_sync(self, currentRoom):
		logger.debug("Map synced to {}, vnum {}".format(currentRoom, currentRoom.vnum))
		# reset player position, center the map around
		self.playerRoom = currentRoom
		self.draw_map(currentRoom)

	def on_gui_refresh(self):
		'''This event is fired when the mapper needs to signal the GUI to clear the visible rooms cache and redraw the map view.'''
		if self.centerRoom is not None:
			self.draw_map(self.centerRoom)
			logger.debug('GUI refreshed.')
		else:
			logger.debug('Unable to refresh the GUI. The center room is not defined.')

	def draw_map(self, centerRoom):
		logger.debug("Drawing rooms around {}".format(centerRoom))
		# reset the recorded state of the window
		self.sprites = []
		self.visibleRooms = {}
		self.centerRoom = centerRoom
		# draw the rooms, beginning by the central one
		self.draw_room(self.mcol, self.mrow, centerRoom)
		for vnum, room, x, y, z in self.world.getNeighborsFromRoom(
				start=centerRoom, radius=self.radius
				):
			if z == 0:
				self.draw_room(self.mcol + x, self.mrow + y, room)
		self.draw_player()

	def draw_room(self, x, y, room):
		logger.debug("Drawing room: {} {} {}".format(x, y, room))
		self.visibleRooms[x, y] = room
		# draw the terrain on layer 0
		self.draw_tile(x, y, 0, room.terrain)
		# draw the walls on layer 1
		for exit in ('north', 'east', 'south', 'west'):
			if exit not in room.exits:
				self.draw_tile(x, y, 1, "wall" + exit)
		# draw the arrows for exits up and down on layer 1
		for exit in ('up', 'down'):
			if exit in room.exits:
				self.draw_tile(x, y, 1, "exit" + exit)
		# draw a single load flag on layer 2
		for flag in room.loadFlags:
			if flag in ('attention', 'treasure', 'key', 'armour', 'weapon', 'herb'):
				self.draw_tile(x, y, 2, flag)
				break
		# draw a single mob flag on layer 2
		for flag in room.mobFlags:
			if flag in ('smob', 'rent', 'quest'):
				self.draw_tile(x, y, 2, flag)
				break
			if search('shop', flag):
				self.draw_tile(x, y, 2, 'shop')
				break
			if search('guild', flag):
				self.draw_tile(x, y, 2, 'guild')
				break


	def draw_player(self):
		if self.playerRoom == None or self.centerRoom == None:
		    return
		logger.debug("Drawing player on room vnum {}".format(self.playerRoom.vnum))
		# transform map coordinates to window ones
		x = self.playerRoom.x - self.centerRoom.x + self.mcol
		y = self.playerRoom.y - self.centerRoom.y + self.mrow
		z = self.playerRoom.z - self.centerRoom.z
		# Be sure the player coordinates are part of the window
		if z == 0 and x >= 0 and x < self.col and y >= 0 and y < self.row:
			# draw the player on layer 3
			self.draw_tile(x, y, 3, "player")

	def draw_tile(self, x, y, z, tile):
		logger.debug("Drawing tile: {} {} {}".format(x, y, tile))
		# pyglet stuff to add a sprite to the batch
		sprite = pyglet.sprite.Sprite(TILES[tile], batch=self.batch, group=self.layer[z])
		# adapt sprite coordinates
		sprite.x = x * self.square
		sprite.y = y * self.square
		# add the sprite to the list of visible sprites
		self.sprites.append(sprite)

	def on_mouse_press(self, wx, wy, buttons, modifiers):
		logger.debug("Mouse press on {} {}.".format(wx, wy))
		x = int(wx / self.square)
		y = int(wy / self.square)
		# check if the player clicked on a room
		# searching for the tuple of coordinates (x, y)
		try:
			room = self.visibleRooms[x, y]
		except KeyError:
			return
		# Action depends on which button the player clicked
		if buttons == pyglet.window.mouse.LEFT:
		    # center the map on the selected room
		    self.draw_map(room)
		elif buttons == pyglet.window.mouse.MIDDLE:
		    # center the map on the player
		    self.draw_map(self.playerRoom)
		elif buttons == pyglet.window.mouse.RIGHT:
		    # print the vnum
		    self.world.output("Click on room {}.".format(room.vnum))


Window.register_event_type('on_map_sync')
Window.register_event_type('on_gui_refresh')
