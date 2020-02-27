# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Some code borrowed from pymunk's debug drawing functions.


from collections import namedtuple
from itertools import chain
import logging
import math
try:
	from Queue import Empty as QueueEmpty
except ImportError:
	from queue import Empty as QueueEmpty

import pyglet
from pyglet.window import key
try:
	from speechlight import Speech
except ImportError:
	Speech = None

from .vec2d import Vec2d
from ..config import Config, config_lock
from ..world import DIRECTIONS


FPS = 30
DIRECTIONS_2D = set(DIRECTIONS[:-2])

DIRECTIONS_VEC2D = {
	"north": Vec2d(0, 1),
	"east": Vec2d(1, 0),
	"south": Vec2d(0, -1),
	"west": Vec2d(-1, 0)
}

KEYS = {
	(key.ESCAPE, 0): "reset_zoom",
	(key.LEFT, 0): "adjust_size",
	(key.RIGHT, 0): "adjust_size",
	(key.UP, 0): "adjust_gap",
	(key.DOWN, 0): "adjust_gap",
	(key.F11, 0): "toggle_fullscreen",
	(key.F12, 0): "toggle_blink",
	(key.SPACE, 0): "toggle_continuous_view"
}

TERRAIN_COLORS = {
	"brush": (127, 255, 0, 255),
	"cavern": (153, 50, 204, 255),
	"city": (190, 190, 190, 255),
	"field": (124, 252, 0, 255),
	"deathtrap": (255, 128, 0, 255),
	"forest": (8, 128, 0, 255),
	"highlight": (0, 0, 255, 255),
	"hills": (139, 69, 19, 255),
	"indoors": (186, 85, 211, 255),
	"mountains": (165, 42, 42, 255),
	"rapids": (32, 64, 192, 255),
	"road": (255, 255, 255, 255),
	"shallow": (218, 120, 245, 255),
	"tunnel": (153, 50, 204, 255),
	"underwater": (48, 8, 120, 255),
	"undefined": (24, 16, 32, 255),
	"water": (32, 64, 192, 255)
}

pyglet.options["debug_gl"] = False
logger = logging.getLogger(__name__)


class Color(namedtuple("Color", ["r", "g", "b", "a"])):
	"""Color tuple used by the debug drawing API.
	"""
	__slots__ = ()

	def as_int(self):
		return tuple(int(i) for i in self)

	def as_float(self):
		return tuple(i / 255.0 for i in self)


class Blinker(object):
	def __init__(self, blink_rate, draw_func, args_func):
		logger.debug(
			"Creating blinker with blink rate {}, calling function {}, with {} for arguments.".format(
				blink_rate,
				draw_func,
				args_func
			)
		)
		self.blink_rate = blink_rate
		self.draw_func = draw_func
		self.args_func = args_func
		self.since = 0
		self.vl = None

	def blink(self, dt):
		self.since += dt
		if self.since >= 1.0 / self.blink_rate:
			if self.vl is None:
				logger.debug("{} blink on. Drawing.".format(self))
				args, kwargs = self.args_func()
				self.vl = self.draw_func(*args, **kwargs)
			else:
				logger.debug("{} blink off. Cleaning upp".format(self))
				self.vl.delete()
				self.vl = None
			self.since = 0

	def delete(self):
		if self.vl is not None:
			self.vl.delete()
			self.vl = None

	def __del__(self):
		self.delete()


class Window(pyglet.window.Window):
	def __init__(self, world):
		self.world = world
		self._gui_queue = world._gui_queue
		self._gui_queue_lock = world._gui_queue_lock
		if Speech is not None:
			self._speech = Speech()
			self.say = self._speech.say
		else:
			self.say = lambda *args, **kwargs: None
			msg = (
				"Speech disabled. Unable to import speechlight. Please download from:\n"
				"https://github.com/nstockton/speechlight"
			)
			self.message(msg)
			logger.warning(msg)
		self._cfg = {}
		with config_lock:
			cfg = Config()
			if "gui" in cfg:
				self._cfg.update(cfg["gui"])
			else:
				cfg["gui"] = {}
				cfg.save()
			del cfg
		if "fullscreen" not in self._cfg:
			self._cfg["fullscreen"] = False
		terrain_colors = {}
		terrain_colors.update(TERRAIN_COLORS)
		if "terrain_colors" in self._cfg:
			terrain_colors.update(self._cfg["terrain_colors"])
		self._cfg["terrain_colors"] = terrain_colors
		self.continuous_view = True
		self.batch = pyglet.graphics.Batch()
		self.groups = tuple(pyglet.graphics.OrderedGroup(i) for i in range(6))
		self.visible_rooms = {}
		self.visible_exits = {}
		self.blinkers = {}
		self.center_mark = []
		self.highlight = None
		self.current_room = None
		super(Window, self).__init__(caption="MPM", resizable=True, vsync=False, fullscreen=self._cfg["fullscreen"])
		logger.info("Created window {}".format(self))
		pyglet.clock.schedule_interval_soft(self.queue_observer, 1.0 / FPS)
		if self.blink:
			# If blinking was enabled in the cconfig file, resetting self.blink
			# to True will trigger the initial scheduling of the blinker in the clock.
			self.blink = True

	@property
	def size(self):
		"""The size of a drawn room in pixels."""
		try:
			if not 20 <= int(self._cfg["room_size"]) <= 300:
				raise ValueError
		except KeyError:
			self._cfg["room_size"] = 100
		except ValueError:
			logger.warn("Invalid value for room_size in config.json: {}".format(self._cfg["room_size"]))
			self._cfg["room_size"] = 100
		return int(self._cfg["room_size"])

	@size.setter
	def size(self, value):
		value = int(value)
		if value < 20:
			value = 20
		elif value > 300:
			value = 300
		self._cfg["room_size"] = value

	@property
	def size_as_float(self):
		"""The scale of a drawn room."""
		return self.size / 100.0

	@property
	def gap(self):
		try:
			if not 10 <= self._cfg["gap"] <= 100:
				raise ValueError
		except KeyError:
			self._cfg["gap"] = 100
		except ValueError:
			logger.warning("Invalid value for gap in config.json: {}".format(self._cfg["gap"]))
			self._cfg["gap"] = 100
		return int(self._cfg["gap"])

	@gap.setter
	def gap(self, value):
		value = int(value)
		if value < 10:
			value = 10
		elif value > 100:
			value = 100
		self._cfg["gap"] = value

	@property
	def gap_as_float(self):
		return self.gap / 100.0

	@property
	def blink(self):
		return bool(self._cfg.get("blink", True))

	@blink.setter
	def blink(self, value):
		value = bool(value)
		self._cfg["blink"] = value
		if value:
			pyglet.clock.schedule_interval_soft(self.blinker, 1.0 / 20)
			self.enable_current_room_markers()
		else:
			pyglet.clock.unschedule(self.blinker)
			for marker in self.blinkers["current_room_markers"]:
				marker.delete()
			del self.blinkers["current_room_markers"]

	@property
	def blink_rate(self):
		try:
			if not 0 <= int(self._cfg["blink_rate"]) <= 15:
				raise ValueError
		except KeyError:
			self._cfg["blink_rate"] = 2
		except ValueError:
			logger.warning("Invalid value for blink_rate in config.json: {}".format(self._cfg["blink_rate"]))
			self._cfg["blink_rate"] = 2
		return int(self._cfg["blink_rate"])

	@blink_rate.setter
	def blink_rate(self, value):
		value = int(value)
		if value < 0:
			value = 0
		elif value > 15:
			value = 15
		self._cfg["blink_rate"] = value

	@property
	def current_room_mark_radius(self):
		try:
			if not 1 <= int(self._cfg["current_room_mark_radius"]) <= 100:
				raise ValueError
		except KeyError:
			self._cfg["current_room_mark_radius"] = 10
		except ValueError:
			logger.warning(
				"Invalid value for current_room_mark_radius: {}".format(
					self._cfg["current_room_mark_radius"]
				)
			)
			self._cfg["current_room_mark_radius"] = 10
		return int(self._cfg["current_room_mark_radius"])

	@property
	def current_room_mark_color(self):
		try:
			return Color(*self._cfg["current_room_mark_color"])
		except KeyError:
			self._cfg["current_room_mark_color"] = (255, 255, 255, 255)
			return Color(*self._cfg["current_room_mark_color"])

	@property
	def terrain_colors(self):
		try:
			return self._cfg["terrain_colors"]
		except KeyError:
			self._cfg["terrain_colors"] = TERRAIN_COLORS
			return self._cfg["terrain_colors"]

	@property
	def cx(self):
		return self.width / 2.0

	@property
	def cy(self):
		return self.height / 2.0

	@property
	def cp(self):
		return Vec2d(self.cx, self.cy)

	@property
	def room_draw_radius(self):
		space = 1 if self.continuous_view else self.gap_as_float + 1.0
		return (
			int(math.ceil(self.width / self.size / space / 2)),
			int(math.ceil(self.height / self.size / space / 2)),
			1
		)

	def room_offset_from_pixels(self, x, y, z=None):
		"""
		Given a pair of X-Y coordinates in pixels, return the
		offset in room coordinates from the center room.
		"""
		return (
			int((x - self.cx + self.size / 2) // self.size),
			int((y - self.cy + self.size / 2) // self.size)
		)

	def message(self, text):
		self.say(text)
		self.world.output(text)

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

	def blinker(self, dt):
		for _, marker in self.blinkers.items():
			try:
				marker.blink(dt)
			except AttributeError:
				for submarker in marker:
					submarker.blink(dt)

	def on_close(self):
		logger.debug("Closing window {}".format(self))
		with config_lock:
			cfg = Config()
			cfg["gui"].update(self._cfg)
			cfg.save()
			del cfg
		super(Window, self).on_close()

	def on_draw(self):
		pyglet.gl.glClearColor(0, 0, 0, 0)
		self.clear()
		self.batch.draw()

	def on_map_sync(self, currentRoom):
		logger.debug("Map synced to {}".format(currentRoom))
		self.current_room = currentRoom
		self.redraw()

	def on_gui_refresh(self):
		"""
		This event is fired when the mapper needs to signal the GUI to clear the
		visible rooms cache and redraw the map view.
		"""
		logger.debug("Clearing visible exits.")
		for dead in self.visible_exits:
			try:
				try:
					for d in self.visible_exits[dead]:
						d.delete()
				except TypeError:
					self.visible_exits[dead].delete()
			except AssertionError:
				pass
		self.visible_exits.clear()
		logger.debug("Clearing visible rooms.")
		for dead in self.visible_rooms:
			self.visible_rooms[dead][0].delete()
		self.visible_rooms.clear()
		if self.center_mark:
			for i in self.center_mark:
				i.delete()
			del self.center_mark[:]
		self.redraw()
		self.center_mark.append(
			self.draw_circle(
				self.cp,
				self.size / 2.0 / 8 * 3,
				Color(0, 0, 0, 255),
				self.groups[4]
			)
		)
		self.center_mark.append(
			self.draw_circle(
				self.cp,
				self.size / 2.0 / 8,
				Color(255, 255, 255, 255),
				self.groups[5]
			)
		)
		logger.debug("GUI refreshed.")

	def on_resize(self, width, height):
		super(Window, self).on_resize(width, height)
		logger.debug("resizing window to ({}, {})".format(width, height))
		if self.current_room is not None:
			self.on_gui_refresh()

	def on_key_press(self, sym, mod):
		logger.debug("Key press: sym: {}, mod: {}".format(sym, mod))
		key = (sym, mod)
		if key in KEYS:
			funcname = "do_" + KEYS[key]
			try:
				func = getattr(self, funcname)
				try:
					func(sym, mod)
				except Exception as e:
					logger.exception(e.message)
			except AttributeError:
				logger.error("Invalid key assignment for key {}. No such function {}.".format(key, funcname))

	def on_mouse_motion(self, x, y, dx, dy):
		for vnum, item in self.visible_rooms.items():
			vl, room, cp = item
			if self.room_offset_from_pixels(*cp) == self.room_offset_from_pixels(x, y):
				if vnum is None or vnum not in self.world.rooms:
					return
				elif self.highlight == vnum:
					# Room already highlighted.
					return
				self.highlight = vnum
				self.say("{}, {}".format(room.name, vnum), True)
				break
		else:
			self.highlight = None
		self.on_gui_refresh()

	def on_mouse_press(self, x, y, buttons, modifiers):
		logger.debug("Mouse press on {} {}, buttons: {}, modifiers: {}".format(x, y, buttons, modifiers))
		if buttons == pyglet.window.mouse.MIDDLE:
			self.do_reset_zoom(key.ESCAPE, 0)
			return
		# check if the player clicked on a room
		for vnum, item in self.visible_rooms.items():
			vl, room, cp = item
			if self.room_offset_from_pixels(*cp) == self.room_offset_from_pixels(x, y):
				# Action depends on which button the player clicked
				if vnum is None or vnum not in self.world.rooms:
					return
				elif buttons == pyglet.window.mouse.LEFT:
					if modifiers & key.MOD_SHIFT:
						# print the vnum
						self.world.output("{}, {}".format(vnum, room.name))
					else:
						result = self.world.path(vnum)
						if result is not None:
							self.world.output(result)
				elif buttons == pyglet.window.mouse.RIGHT:
					self.world.currentRoom = room
					self.world.output("Current room now set to '{}' with vnum {}".format(room.name, vnum))
				break

	def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
		if scroll_y > 0:
			self.do_adjust_size(key.RIGHT, 0)
		elif scroll_y < 0:
			self.do_adjust_size(key.LEFT, 0)

	def on_mouse_leave(self, x, y):
		self.highlight = None
		self.on_gui_refresh()

	def do_toggle_blink(self, sym, mod):
		self.blink = not self.blink
		self.say("Blinking {}".format("enabled" if self.blink else "disabled"), True)

	def do_toggle_continuous_view(self, sym, mod):
		self.continuous_view = not self.continuous_view
		self.say("{} view".format("continuous" if self.continuous_view else "tiled"), True)
		self.on_gui_refresh()

	def do_toggle_fullscreen(self, sym, mod):
		fs = not self.fullscreen
		self.set_fullscreen(fs)
		self._cfg["fullscreen"] = fs
		self.say("fullscreen {}.".format("enabled" if fs else "disabled"), True)

	def do_adjust_gap(self, sym, mod):
		self.continuous_view = False
		if sym == key.DOWN:
			self.gap -= 10
		elif sym == key.UP:
			self.gap += 10
		self.say("{} Gap.".format(self.gap_as_float), True)
		self.on_gui_refresh()

	def do_adjust_size(self, sym, mod):
		if sym == key.LEFT:
			self.size -= 10
		elif sym == key.RIGHT:
			self.size += 10
		self.say("{}%".format(self.size), True)
		self.on_gui_refresh()

	def do_reset_zoom(self, sym, mod):
		self.size = 100
		self.on_gui_refresh()
		self.say("Reset zoom", True)

	def circle_vertices(self, cp, radius):
		cp = Vec2d(cp)
		# http://slabode.exofire.net/circle_draw.shtml
		numSegments = int(4 * math.sqrt(radius))
		theta = float(2 * math.pi / numSegments)
		radialFactor = math.cos(theta)
		sine = math.sin(theta)
		x = radius  # We start at angle 0.
		y = 0
		points = []
		for _ in range(numSegments):
			points.append(cp + (x, y))
			tangent = x
			x = x * radialFactor - y * sine
			y = y * radialFactor + tangent * sine
		vertices = points[0:1] * 2  # The first point, twice.
		vertices.extend(chain.from_iterable((points[i], points[-i]) for i in range(1, (len(points) + 1) // 2)))
		vertices.append(vertices[-1])
		return list(chain.from_iterable(vertices))

	def draw_circle(self, cp, radius, color, group=None):
		vertices = self.circle_vertices(cp, radius)
		count = len(vertices) // 2
		return self.batch.add(
			count,
			pyglet.gl.GL_TRIANGLE_STRIP,
			group,
			("v2f", vertices),
			("c4B", color.as_int() * count)
		)

	def draw_segment(self, a, b, color, group=None):
		vecA = Vec2d(a)
		vecB = Vec2d(b)
		vertices = (int(vecA.x), int(vecA.y), int(vecB.x), int(vecB.y))
		count = len(vertices) // 2
		return self.batch.add(
			count,
			pyglet.gl.GL_LINES,
			group,
			("v2i", vertices),
			("c4B", color.as_int() * count)
		)

	def fat_segment_vertices(self, a, b, radius):
		vecA = Vec2d(a)
		vecB = Vec2d(b)
		radius = max(radius, 1)
		tangent = -math.atan2(*(vecB - vecA))
		delta = (math.cos(tangent) * radius, math.sin(tangent) * radius)
		points = [
			vecA + delta,
			vecA - delta,
			vecB + delta,
			vecB - delta
		]
		return list(chain.from_iterable([*points[:3], *points[1:]]))

	def draw_fat_segment(self, a, b, radius, color, group=None):
		vertices = self.fat_segment_vertices(a, b, radius)
		count = len(vertices) // 2
		return self.batch.add(
			count,
			pyglet.gl.GL_TRIANGLES,
			group,
			("v2f", vertices),
			("c4B", color.as_int() * count)
		)

	def corners_2_vertices(self, points):
		points.insert(2, points.pop(0))  # Move item 0 to index 2.
		return list(chain.from_iterable([points[0], *points, points[-1]]))

	def draw_polygon(self, points, color, group=None):
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		vertices = self.corners_2_vertices(points)
		count = len(vertices) // 2
		return self.batch.add(
			count,
			mode,
			group,
			("v2f", vertices),
			("c4B", color.as_int() * count)
		)

	def square_vertices(self, cp, radius):
		return [
			cp - (radius, radius),  # Bottom left.
			cp - (radius, -radius),  # Top left.
			cp + (radius, radius),  # Top right.
			cp + (radius, -radius)  # Bottom right.
		]

	def equilateral_triangle(self, cp, radius, angleDegrees):
		vecA = Vec2d(radius, 0)
		vecA.rotate_degrees(angleDegrees)
		vecB = vecA.rotated_degrees(120)
		vecC = vecB.rotated_degrees(120)
		return [vecA + cp, vecB + cp, vecC + cp]

	def arrow_points(self, a, d, radius):
		vec = d - a
		h = math.sqrt(3) * radius * 1.5
		vec.length -= h
		b = a + vec
		vec.length += h / 3.0
		c = a + vec
		return (b, c, vec.angle_degrees)

	def arrow_vertices(self, a, d, radius):
		b, c, angle = self.arrow_points(a, d, radius)
		return (
			self.fat_segment_vertices(a, b, radius),
			self.corners_2_vertices(self.equilateral_triangle(c, radius * 3, angle))
		)

	def draw_arrow(self, a, d, radius, color, group=None):
		b, c, angle = self.arrow_points(a, d, radius)
		return (
			self.draw_fat_segment(a, b, radius, color, group=group),
			self.draw_polygon(self.equilateral_triangle(c, radius * 3, angle), color, group=group)
		)

	def draw_room(self, room, cp, group=None):
		if self.highlight is not None and self.highlight == room.vnum:
			color = Color(*self.terrain_colors.get("highlight", "undefined"))
		else:
			color = Color(*self.terrain_colors.get(room.terrain, "undefined"))
		vertices = self.square_vertices(cp, self.size / 2.0)
		if group is None:
			group = self.groups[0]
		if room.vnum not in self.visible_rooms:
			self.visible_rooms[room.vnum] = [
				self.draw_polygon(vertices, color, group=group),
				room,
				cp
			]
		else:
			roomShape = self.visible_rooms[room.vnum][0]
			roomShape.vertices = self.corners_2_vertices(vertices)
			self.batch.migrate(roomShape, pyglet.gl.GL_TRIANGLE_STRIP, group, self.batch)
			self.visible_rooms[room.vnum][2] = cp

	def draw_rooms(self, currentRoom=None):
		if currentRoom is None:
			currentRoom = self.current_room
		logger.debug("Drawing rooms near {}".format(currentRoom))
		self.draw_room(currentRoom, self.cp, group=self.groups[1])
		newrooms = {currentRoom.vnum}
		neighbors = self.world.getNeighborsFromRoom(start=currentRoom, radius=self.room_draw_radius)
		for vnum, room, x, y, z in neighbors:
			if z == 0:
				newrooms.add(vnum)
				delta = Vec2d(x, y) * (self.size * (1 if self.continuous_view else self.gap_as_float + 1.0))
				self.draw_room(room, self.cp + delta)
		if self.visible_rooms:
			for vnum in set(self.visible_rooms) - newrooms:
				self.visible_rooms[vnum][0].delete()
				del self.visible_rooms[vnum]

	def exitsUpDown(self, direction, exit, name, cp, exitColor1, exitColor2, radius):
		if direction == "up":
			newCP = cp + (0, self.size / 4.0)
			angle = 90
		elif direction == "down":
			newCP = cp - (0, self.size / 4.0)
			angle = -90
		if self.world.isBidirectional(exit):
			vs1 = self.equilateral_triangle(newCP, (self.size / 4.0) + 14, angle)
			vs2 = self.equilateral_triangle(newCP, self.size / 4.0, angle)
			if name in self.visible_exits and isinstance(self.visible_exits[name], tuple):
				vl1, vl2 = self.visible_exits[name]
				vl1.vertices = self.corners_2_vertices(vs1)
				vl2.vertices = self.corners_2_vertices(vs2)
			else:
				if name in self.visible_exits:
					self.visible_exits[name].delete()
				vl1 = self.draw_polygon(vs1, exitColor2, group=self.groups[2])
				vl2 = self.draw_polygon(vs2, exitColor1, group=self.groups[2])
				self.visible_exits[name] = (vl1, vl2)
		elif exit.to in ("undefined", "death"):
			if name in self.visible_exits and not isinstance(self.visible_exits[name], tuple):
				vl = self.visible_exits[name]
				vl.x, vl.y = newCP
			elif exit.to == "undefined":
				self.visible_exits[name] = pyglet.text.Label(
					"?",
					font_name="Times New Roman",
					font_size=(self.size / 100.0) * 72,
					x=newCP.x,
					y=newCP.y,
					anchor_x="center",
					anchor_y="center",
					color=exitColor2,
					batch=self.batch,
					group=self.groups[2]
				)
			else:  # Death
				self.visible_exits[name] = pyglet.text.Label(
					"X",
					font_name="Times New Roman",
					font_size=(self.size / 100.0) * 72,
					x=newCP.x,
					y=newCP.y,
					anchor_x="center",
					anchor_y="center",
					color=Color(255, 0, 0, 255),
					batch=self.batch,
					group=self.groups[2]
				)
		else:  # one-way, random, etc
			vec = newCP - cp
			vec.length /= 2
			a = newCP - vec
			d = newCP + vec
			r = (self.size / radius) / 2.0
			if name in self.visible_exits and isinstance(self.visible_exits[name], tuple):
				vl1, vl2 = self.visible_exits[name]
				vs1, vs2 = self.arrow_vertices(a, d, r)
				vl1.vertices = vs1
				vl2.vertices = vs2
			else:
				if name in self.visible_exits:
					self.visible_exits[name].delete()
				vl1, vl2 = self.draw_arrow(a, d, r, exitColor2, group=self.groups[2])
				self.visible_exits[name] = (vl1, vl2)

	def exits2d(self, direction, exit, name, cp, exitColor1, exitColor2, radius):
		if self.continuous_view:
			name += "-"
			if exit is None:
				color = exitColor2
			elif exit.to == "undefined":
				color = Color(0, 0, 255, 255)
			elif exit.to == "death":
				color = Color(255, 0, 0, 255)
			else:
				color = Color(0, 255, 0, 255)
			square = self.square_vertices(cp, self.size / 2.0)
			a = square[(DIRECTIONS.index(direction) + 1) % 4]
			b = square[(DIRECTIONS.index(direction) + 2) % 4]
			if name in self.visible_exits and not isinstance(self.visible_exits[name], tuple):
				vl = self.visible_exits[name]
				vl.vertices = self.fat_segment_vertices(a, b, self.size / radius / 2.0)
				vl.colors = color * (len(vl.colors) // 4)
			else:
				self.visible_exits[name] = self.draw_fat_segment(
					a,
					b,
					self.size / radius,
					color,
					group=self.groups[2]
				)
		else:
			directionVector = DIRECTIONS_VEC2D.get(direction, None)
			if self.world.isBidirectional(exit):
				a = cp + (directionVector * (self.size / 2.0))
				b = a + (directionVector * ((self.size * self.gap_as_float) / 2))
				if name in self.visible_exits and not isinstance(self.visible_exits[name], tuple):
					vl = self.visible_exits[name]
					vs = self.fat_segment_vertices(a, b, self.size / radius)
					vl.vertices = vs
				else:
					self.visible_exits[name] = self.draw_fat_segment(
						a,
						b,
						self.size / radius,
						exitColor1,
						group=self.groups[2]
					)
			elif exit.to in ("undefined", "death"):
				newCP = cp + directionVector * (self.size * 0.75)
				if name in self.visible_exits and not isinstance(self.visible_exits[name], tuple):
					vl = self.visible_exits[name]
					vl.x, vl.y = newCP
				elif exit.to == "undefined":
					self.visible_exits[name] = pyglet.text.Label(
						"?",
						font_name="Times New Roman",
						font_size=(self.size / 100.0) * 72,
						x=newCP.x,
						y=newCP.y,
						anchor_x="center",
						anchor_y="center",
						color=exitColor1,
						batch=self.batch,
						group=self.groups[2]
					)
				else:  # Death
					self.visible_exits[name] = pyglet.text.Label(
						"X",
						font_name="Times New Roman",
						font_size=(self.size / 100.0) * 72,
						x=newCP.x,
						y=newCP.y,
						anchor_x="center",
						anchor_y="center",
						color=Color(255, 0, 0, 255),
						batch=self.batch,
						group=self.groups[2]
					)
			else:  # One-way, random, etc.
				color = exitColor1
				a = cp + (directionVector * (self.size / 2.0))
				d = a + (directionVector * ((self.size * self.gap_as_float) / 2))
				r = ((self.size / radius) / 2.0) * self.gap_as_float
				if name in self.visible_exits and isinstance(self.visible_exits[name], tuple):
					vl1, vl2 = self.visible_exits[name]
					vs1, vs2 = self.arrow_vertices(a, d, r)
					vl1.vertices = vs1
					vl1.colors = color * (len(vl1.colors) // 4)
					vl2.vertices = vs2
					vl2.colors = color * (len(vl2.colors) // 4)
				else:
					if name in self.visible_exits:
						self.visible_exits[name].delete()
					self.visible_exits[name] = self.draw_arrow(a, d, r, color, group=self.groups[2])

	def getExits(self, room):
		if not self.continuous_view:
			return set(room.exits)  # Normal exits list
		# Swap NESW exits with directions you can't go. Leave up/down in place if present.
		exits = DIRECTIONS_2D.symmetric_difference(room.exits)
		for direction in room.exits:
			if not self.world.isBidirectional(room.exits[direction]):
				# Add any existing NESW exits that are unidirectional back
				# to the exits set for processing later.
				exits.add(direction)
		return exits

	def clearOldVisibleExits(self, newExits):
		for name in set(self.visible_exits) - newExits:
			try:
				try:
					for dead in self.visible_exits[name]:
						dead.delete()
				except TypeError:
					self.visible_exits[name].delete()
			except AssertionError:
				pass
			del self.visible_exits[name]

	def draw_exits(self):
		logger.debug("Drawing exits")
		try:
			exitColor1 = self._cfg["exitColor1"]
		except KeyError:
			exitColor1 = (255, 228, 225, 255)
			self._cfg["exitColor1"] = exitColor1
		try:
			exitColor2 = self._cfg["exitColor2"]
		except KeyError:
			exitColor2 = (0, 0, 0, 255)
			self._cfg["exitColor2"] = exitColor2
		exitColor1 = Color(*exitColor1)
		exitColor2 = Color(*exitColor2)
		try:
			radius = int(self._cfg["exit_radius"])
		except (KeyError, ValueError) as error:
			if isinstance(error, ValueError):
				logger.warning("Invalid value for exit_radius in config.json: {}".format(radius))
			radius = 10
			self._cfg["exit_radius"] = radius
		newExits = set()
		for vnum, item in self.visible_rooms.items():
			vl, room, cp = item
			for direction in self.getExits(room):
				name = vnum + direction
				exit = room.exits.get(direction, None)
				if direction in ("up", "down"):
					self.exitsUpDown(direction, exit, name, cp, exitColor1, exitColor2, radius)
				else:
					self.exits2d(direction, exit, name, cp, exitColor1, exitColor2, radius)
				newExits.add(name)
		self.clearOldVisibleExits(newExits)

	def enable_current_room_markers(self):
		if "current_room_markers" in self.blinkers:
			return
		current_room_markers = []
		current_room_markers.append(
			Blinker(
				self.blink_rate,
				self.draw_circle,
				lambda: (
					(
						self.cp - (self.size / 2.0),
						(self.size / 100.0) * self.current_room_mark_radius,
						self.current_room_mark_color
					),
					{"group": self.groups[5]}
				)
			)
		)
		current_room_markers.append(
			Blinker(
				self.blink_rate,
				self.draw_circle,
				lambda: (
					(
						self.cp - (self.size / 2.0, -self.size / 2.0),
						(self.size / 100.0) * self.current_room_mark_radius,
						self.current_room_mark_color
					),
					{"group": self.groups[5]}
				)
			)
		)
		current_room_markers.append(
			Blinker(
				self.blink_rate,
				self.draw_circle,
				lambda: (
					(
						self.cp + (self.size / 2.0),
						(self.size / 100.0) * self.current_room_mark_radius,
						self.current_room_mark_color
					),
					{"group": self.groups[5]}
				)
			)
		)
		current_room_markers.append(
			Blinker(
				self.blink_rate,
				self.draw_circle,
				lambda: (
					(
						self.cp + (self.size / 2.0, -self.size / 2.0),
						(self.size / 100.0) * self.current_room_mark_radius,
						self.current_room_mark_color
					),
					{"group": self.groups[5]}
				)
			)
		)
		self.blinkers["current_room_markers"] = tuple(current_room_markers)

	def redraw(self):
		logger.debug("Redrawing...")
		self.draw_rooms()
		self.draw_exits()


Window.register_event_type("on_map_sync")
Window.register_event_type("on_gui_refresh")
