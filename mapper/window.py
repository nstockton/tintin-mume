# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
###Some code borrowed from pymunk's debug drawing functions###

from __future__ import division
import logging
import pyglet
pyglet.options['debug_gl'] = False
from pyglet.window import key
try:
	from speechlight import Speech
except ImportError:
	Speech = None
import math
from collections import namedtuple
try:
	from Queue import Empty as QueueEmpty
except ImportError:
	from queue import Empty as QueueEmpty

from .config import Config, config_lock
from .constants import DIRECTIONS, TERRAIN_COLORS
from .utils import iterItems
from .vec2d import Vec2d

# Monkey patch range with xrange in Python2.
_range = range
try:
	range = xrange
except NameError:
	pass

logger = logging.getLogger(__name__)
DIRECTIONS_2D = frozenset(DIRECTIONS[:-2])
FPS = 30
KEYS = {
	(key.ESCAPE, 0): "reset_zoom",
	(key.LEFT, 0): "adjust_size",
	(key.RIGHT, 0): "adjust_size",
	(key.UP, 0): "adjust_spacer",
	(key.DOWN, 0): "adjust_spacer",
	(key.F11, 0): "toggle_fullscreen",
	(key.F12, 0): "toggle_blink",
	(key.SPACE, 0): "toggle_continuous_view"
}


DIRECTIONS_VEC2D = {
	"north": Vec2d(0, 1),
	"east": Vec2d(1, 0),
	"south": Vec2d(0, -1),
	"west": Vec2d(-1, 0)
}


class Color(namedtuple("Color", ["r", "g", "b", "a"])):
	"""Color tuple used by the debug drawing API.
	"""
	__slots__ = ()

	def as_int(self):
		return int(self[0]), int(self[1]), int(self[2]), int(self[3])

	def as_float(self):
		return self[0] / 255.0, self[1] / 255.0, self[2] / 255.0, self[3] / 255.0

class Blinker(object):
	def __init__(self, blink_rate, draw_func, args_func):
		logger.debug("Creating blinker with blink rate {}, calling function {}, with {} for arguments.".format(blink_rate, draw_func, args_func))
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
		with config_lock:
			cfg = Config()
			if "gui" not in cfg:
				cfg["gui"] = {}
				cfg.save()
			self._cfg = cfg["gui"]
			del cfg
			if "fullscreen" not in self._cfg:
				self._cfg["fullscreen"] = False
		caption = "MPM"
		self.world = world
		super(Window, self).__init__(caption=caption, resizable=True, vsync=False, fullscreen=self._cfg["fullscreen"])
		logger.info("Creating window {}".format(self))
		if Speech is not None:
			self.speech = Speech()
			self.say = self.speech.say
		else:
			self.say = lambda *args, **kwargs: None
			msg = "Speech disabled. Unable to import speechlight. Please download from:\nhttps://github.com/nstockton/speechlight.git"
			self.message(msg)
			logger.warning(msg)
		self._gui_queue = world._gui_queue
		self._gui_queue_lock = world._gui_queue_lock
		self.batch = pyglet.graphics.Batch()
		self.visible_rooms = {}
		self.visible_exits = {}
		self.blinkers = {}
		self.oldspacer = None
		pyglet.clock.schedule_interval_soft(self.queue_observer, 1.0 / FPS)
		self.current_room = None
		if self.blink:
			pyglet.clock.schedule_interval_soft(self.blinker, 1.0 / 20)
			self.enable_current_room_markers()
		self.groups = tuple(pyglet.graphics.OrderedGroup(i) for i in range(6))

	@property
	def size(self):
		try:
			value = int(self._cfg["room_size"])
			if not 0 <= value <= 250:
				raise ValueError
			return value
		except KeyError:
			self._cfg["room_size"] = 100
		except ValueError:
			logger.warn("Invalid value for room_size in config.json: {}".format(self._cfg['room_size']))
			self._cfg["room_size"] = 100
		return self._cfg["room_size"]
	@size.setter
	def size(self, value):
		value = int(value)
		if value < 50:
			value = 50
		elif value > 250:
			value = 250
		self._cfg["room_size"] = value

	@property
	def spacer(self):
		try:
			value = self._cfg["spacer"]
			if isinstance(value, int):
				if not 0 <= value <= 20:
					raise ValueError
			elif isinstance(value, float):
				if not 0.0 <= value <= 2.0:
					raise ValueError
				self._cfg["spacer"] = int(value * 10)
			else:
				raise ValueError
		except KeyError:
			self._cfg["spacer"] = 10
		except ValueError:
			logger.warning("Invalid value for spacer in config.json: {}".format(value))
			self._cfg["spacer"] = 10
		return self._cfg["spacer"]
	@spacer.setter
	def spacer(self, value):
		value = int(value)
		if value < 0:
			value = 0
		elif value > 20:
			value = 20
		self._cfg["spacer"] = value

	@property
	def spacer_as_float(self):
		return self.spacer / 10.0

	@property
	def blink(self):
		try:
			return bool(self._cfg["blink"])
		except KeyError:
			self._cfg["blink"] = True
			return self._cfg["blink"]
	@blink.setter
	def blink(self, value):
		value = bool(value)
		self._cfg["blink"] = value
		if value:
			pyglet.clock.schedule_interval_soft(self.blinker, 1.0 / 20)
			self.enable_current_room_markers()
		else:
			pyglet.clock.unschedule(self.blinker)
			markers = self.blinkers["current_room_markers"]
			del self.blinkers["current_room_markers"]
			for marker in markers:
				marker.delete()

	@property
	def blink_rate(self):
		try:
			value = int(self._cfg["blink_rate"])
			if not 0 <= value <= 15:
				raise ValueError
			return value
		except KeyError:
			self._cfg["blink_rate"] = 2
		except ValueError:
			logger.warning("Invalid value for blink_rate in config.json: {}".format(value))
			self._cfg["blink_rate"] = 2
		return self._cfg["blink_rate"]
	@blink_rate.setter
	def blink_rate(self, value):
		value = int(value)
		if value < 0:
			value = 0
		elif value > 15:
			value = 15
		self._cfg['blink_rate'] = value

	@property
	def current_room_mark_radius(self):
		try:
			value = int(self._cfg["current_room_mark_radius"])
			if value < 1:
				value = 1
			elif value > 100:
				value = 100
			return value
		except KeyError:
			self._cfg["current_room_mark_radius"] = 10
		except ValueError:
			logger.warning("Invalid value for current_room_mark_radius: {}".format(value))
			self._cfg["current_room_mark_radius"] = 10
		return self._cfg["current_room_mark_radius"]

	@property
	def current_room_mark_color(self):
		try:
			return Color(*self._cfg["current_room_mark_color"])
		except KeyError:
			color = (255, 255, 255, 255)
			self._cfg["current_room_mark_color"] = color
			return Color(*color)

	@property
	def terrain_colors(self):
		try:
			return self._cfg["terrain_colors"]
		except KeyError:
			self._cfg["terrain_colors"] = TERRAIN_COLORS
			return TERRAIN_COLORS

	@property
	def cx(self):
		return self.width / 2.0

	@property
	def cy(self):
		return self.height / 2.0

	@property
	def cp(self):
		return Vec2d(self.cx, self.cy)

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
		for key, marker in iterItems(self.blinkers):
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

	def on_resize(self, width, height):
		super(Window, self).on_resize(width, height)
		logger.debug("resizing window to ({}, {})".format(width, height))
		if self.current_room is not None:
			self.redraw()

	def on_key_press(self, sym, mod):
		logger.debug("Key press: sym: {}, mod: {}".format(sym, mod))
		key = (sym, mod)
		if key in KEYS:
			funcname = "do_" + KEYS[key]
			try:
				func=getattr(self, funcname)
				try:
					func(sym, mod)
				except Exception as e:
					logger.exception(e.message)
			except AttributeError:
				logger.error("Invalid key assignment for key {}. No such function {}.".format(key, funcname))

	def do_toggle_blink(self, sym, mod):
		self.blink = not self.blink
		self.say("Blinking {}".format({True: "enabled", False: "disabled"}[self.blink]))

	def do_toggle_continuous_view(self, sym, mod):
		if self.oldspacer is None and self.spacer:
			self.oldspacer, self.spacer = self.spacer, 0
			self.say("continuous view")
		elif self.oldspacer is not None:
			self.spacer, self.oldspacer = self.oldspacer, None
			self.say("Tiled view")
		else:
			return
		self.redraw()

	def do_toggle_fullscreen(self, sym, mod):
		fs = not self.fullscreen
		self.set_fullscreen(fs)
		self._cfg["fullscreen"] = fs
		self.say("fullscreen {}".format({True: "enabled", False: "disabled"}[fs]))

	def do_adjust_spacer(self, sym, mod):
		if self.oldspacer is not None:
			self.oldspacer = None
		if sym == key.DOWN:
			self.spacer -= 1
		elif sym == key.UP:
			self.spacer += 1
		self.say(str(self.spacer_as_float))
		self.redraw()

	def do_adjust_size(self, sym, mod):
		if sym == key.LEFT:
			self.size -= 10.0
		elif sym == key.RIGHT:
			self.size += 10.0
		self.say(str(self.size))
		self.redraw()

	def do_reset_zoom(self, sym, mod):
		self.size = 100
		self.spacer = 10
		self.oldspacer = None
		self.redraw()
		self.say("Reset zoom")

	def circle_vertices(self, cp, radius):
		cp = Vec2d(cp)
		# http://slabode.exofire.net/circle_draw.shtml
		num_segments = int(4 * math.sqrt(radius))
		theta = 2 * math.pi / num_segments
		c = math.cos(theta)
		s = math.sin(theta)
		x = radius # we start at angle 0
		y = 0
		ps = []
		for i in range(num_segments):
			ps += [Vec2d(cp.x + x, cp.y + y)]
			t = x
			x = c * x - s * y
			y = s * t + c * y
		ps2 = [ps[0]]
		for i in range(1, int((len(ps) + 1) // 2)):
			ps2.append(ps[i])
			ps2.append(ps[-i])
		ps = ps2
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
			vs += [p.x, p.y]
		return vs

	def draw_circle(self, cp, radius, color, group=None):
		vs = self.circle_vertices(cp, radius)
		l = len(vs) // 2
		return self.batch.add(l, pyglet.gl.GL_TRIANGLE_STRIP, group,
				("v2f", vs),
				("c4B", color.as_int() * l))

	def draw_segment(self, a, b, color, group=None):
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		line = (int(pv1.x), int(pv1.y), int(pv2.x), int(pv2.y))
		return self.batch.add(2, pyglet.gl.GL_LINES, group,
				("v2i", line),
				("c4B", color.as_int() * 2))

	def fat_segment_vertices(self, a, b, radius): 
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		d = pv2 - pv1
		a = -math.atan2(d.x, d.y)
		radius = max(radius, 1)
		dx = radius * math.cos(a)
		dy = radius * math.sin(a)
		p1 = pv1 + Vec2d(dx, dy)
		p2 = pv1 - Vec2d(dx, dy)
		p3 = pv2 + Vec2d(dx, dy)
		p4 = pv2 - Vec2d(dx, dy)
		vs = [i for xy in [p1, p2, p3] + [p2, p3, p4] for i in xy]
		return vs

	def draw_fat_segment(self, a, b, radius, color, group=None):
		vs = self.fat_segment_vertices(a, b, radius)
		l = len(vs) // 2
		return self.batch.add(l, pyglet.gl.GL_TRIANGLES, group,
				("v2f", vs),
				("c4B", color.as_int() * l))

	def corners_2_vertices(self, ps):
		ps = [ps[1], ps[2], ps[0]] + ps[3:]
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
			vs += [p.x, p.y]
		return vs

	def draw_polygon(self, verts, color, group=None):
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		vs = self.corners_2_vertices(verts)
		l = len(vs) // 2
		return self.batch.add(l, mode, group,
				("v2f", vs),
				("c4B", color.as_int() * l))

	@property
	def cx(self):
		return self.width / 2.0

	@property
	def cy(self):
		return self.height / 2.0

	@property
	def cp(self):
		return Vec2d(self.cx, self.cy)

	def num_rooms_to_draw(self):
		rooms_w = (self.width // self.size) // 2
		rooms_h = (self.height // self.size) // 2
		return (rooms_w, rooms_h, 1)

	def _draw_current_room_border(self):
		cp = self.cp
		d1 = (self.size / 2.0) * (1.0 + self.current_room_border1)
		vs1 = [cp - d1, cp - (d1, d1 * -1), cp + d1, cp + (d1, d1 * -1)]
		d2 = d1 * (1.0 + self.current_room_border)
		vs2 = [cp - d2, cp - (d2, d2 * -1), cp + d2, cp + (d2, d2 * -1)]
		if self.current_room_border_vl is None:
			vl1 = self.draw_polygon(vs1, Color(0, 0, 0, 255), group=self.groups[2])
			vl2 = self.draw_polygon(vs2, self.current_room_border_color, group=self.groups[1])
			self.current_room_border_vl = (vl1, vl2)
		else:
			vl1, vl2 = self.current_room_border_vl
			vl1.vertices = self.corners_2_vertices(vs1)
			vs = self.corners_2_vertices(vs2)
			vl2.vertices = vs
			vl2.colors = self.current_room_border_color.as_int() * (len(vs) // 2)

	def equilateral_triangle(self, cp, radius, angle_degrees):
		v = Vec2d(radius, 0)
		v.rotate_degrees(angle_degrees)
		w = v.rotated_degrees(120)
		y = w.rotated_degrees(120)
		return [v + cp, w + cp, y + cp]

	def square_from_cp(self, cp, d):
		return [cp - d, cp - (d, d * -1), cp + d, cp + (d, d * -1)]

	def arrow_points(self, a, d, r):
		l = d - a
		h = (r * 1.5) * math.sqrt(3)
		l.length -= h
		b = a + l
		l.length += h / 3.0
		c = a + l
		return (b, c, l.angle_degrees)

	def arrow_vertices(self, a, d, r):
		b, c, angle = self.arrow_points(a, d, r)
		vs1 = self.fat_segment_vertices(a, b, r)
		vs2 = self.corners_2_vertices(self.equilateral_triangle(c, r * 3, angle))
		return (vs1, vs2)

	def draw_arrow(self, a, d, radius, color, group=None):
		b, c, angle = self.arrow_points(a, d, radius)
		vl1 = self.draw_fat_segment(a, b, radius, color, group=group)
		vl2 = self.draw_polygon(self.equilateral_triangle(c, radius * 3, angle), color, group=group)
		return (vl1, vl2)

	def draw_room(self, room, cp, group=None):
		try:
			color = Color(*self.terrain_colors[room.terrain])
		except KeyError as e:
			#self.world.output("Unknown terrain type '{}' @{}!".format(e.args[0], room.vnum))
			color = Color(*self.terrain_colors["unknown"])
		d = self.size / 2.0
		vs = self.square_from_cp(cp, d)
		if group is None:
			group = self.groups[0]
		if room.vnum not in self.visible_rooms:
			vl = self.draw_polygon(vs, color, group=group)
			self.visible_rooms[room.vnum] = [vl, room, cp]
		else:
			vl=self.visible_rooms[room.vnum][0]
			vl.vertices = self.corners_2_vertices(vs)
			self.batch.migrate(vl, pyglet.gl.GL_TRIANGLE_STRIP, group, self.batch)
			self.visible_rooms[room.vnum][2] = cp

	def draw_rooms(self, current_room=None):
		if current_room is None:
			current_room = self.current_room
			logger.debug("Drawing rooms near {}".format(current_room))
		self.draw_room(current_room, self.cp, group=self.groups[3])
		newrooms = {current_room.vnum}
		for vnum, room, x, y, z in self.world.getNeighborsFromRoom(start=current_room, radius=self.num_rooms_to_draw()):
			if z == 0:
				newrooms.add(vnum)
				d = Vec2d(x, y) * (self.size * (self.spacer_as_float + 1.0))
				self.draw_room(room, self.cp + d)
		if not self.visible_rooms:
			return
		for dead in set(self.visible_rooms) - newrooms:
			self.visible_rooms[dead][0].delete()
			del self.visible_rooms[dead]

	def draw_exits(self):
		logger.debug("Drawing exits")
		try:
			exit_color1 = self._cfg["exit_color1"]
		except KeyError:
			exit_color1 = (255, 228, 225, 255)
			self._cfg["exit_color1"] = exit_color1
		try:
			exit_color2 = self._cfg["exit_color2"]
		except KeyError:
			exit_color2 = (0, 0, 0, 255)
			self._cfg["exit_color2"] = exit_color2
		exit_color1 = Color(*exit_color1)
		exit_color2 = Color(*exit_color2)
		try:
			radius = self._cfg['exit_radius']
			if not isinstance(radius, int):
				raise ValueError
		except KeyError:
			radius = 10
			self._cfg["exit_radius"] = radius
		except ValueError:
			logger.warning("Invalid value for exit_radius in config.json: {}".format(radius))
			radius = 10
			self._cfg["exit_radius"] = radius
		_d = self.size / 2
		newexits = set()
		for vnum, item in iterItems(self.visible_rooms):
			vl, room, cp = item
			exits = set(room.exits) # normal exits list
			if not self.spacer:
				exits = set(DIRECTIONS_2D - exits) # swap NESW exits with directions you can't go. Leave up/down in place if present.
				for direction in room.exits:
					if not self.world.isExitLogical(room.exits[direction]):
						exits.add(direction) # add any existing NESW exits that are illogical back to the exits set for processing later.
			for direction in exits:
				name = vnum + direction[0]
				exit = room.exits.get(direction, None)
				dv = DIRECTIONS_VEC2D.get(direction, None)
				if direction in ("up", "down"):
					if direction == "up":
						new_cp = cp + (0, self.size / 4.0)
						angle = 90
					elif direction == "down":
						new_cp = cp - (0, self.size / 4.0)
						angle = -90
					if self.world.isExitLogical(exit):
						vs1 = self.equilateral_triangle(new_cp, (self.size / 4.0) + 14, angle)
						vs2 = self.equilateral_triangle(new_cp, self.size / 4.0, angle)
						if name in self.visible_exits:
							vl1, vl2 = self.visible_exits[name]
							vl1.vertices = self.corners_2_vertices(vs1)
							vl2.vertices = self.corners_2_vertices(vs2)
						else:
							vl1 = self.draw_polygon(vs1, exit_color2, group=self.groups[4])
							vl2 = self.draw_polygon(vs2, exit_color1, group=self.groups[4])
							self.visible_exits[name] = (vl1, vl2)
					elif exit.to in ("undefined", "death"):
						if name in self.visible_exits:
							vl = self.visible_exits[name]
							try:
								vl.x, vl.y = new_cp
							except AttributeError:
								pass
						elif exit.to == "undefined":
							self.visible_exits[name] = pyglet.text.Label("?", font_name="Times New Roman", font_size=(self.size / 100.0) * 72, x=new_cp.x, y=new_cp.y, anchor_x="center", anchor_y="center", color=exit_color2, batch=self.batch, group=self.groups[4])
						else: # Death
							self.visible_exits[name] = pyglet.text.Label("X", font_name="Times New Roman", font_size=(self.size / 100.0) * 72, x=new_cp.x, y=new_cp.y, anchor_x="center", anchor_y="center", color=Color(255, 0, 0, 255), batch=self.batch, group=self.groups[4])
					else: # one-way, random, etc
						l = new_cp - cp
						l.length /= 2
						a = new_cp - l
						d = new_cp + l
						r = (self.size / radius) / 2.0
						if name in self.visible_exits:
							try:
								vl1, vl2 = self.visible_exits[name]
								vs1, vs2 = self.arrow_vertices(a, d, r)
								vl1.vertices = vs1
								vl2.vertices = vs2
							except TypeError:
								pass
						else:
							vl1, vl2 = self.draw_arrow(a, d, r, exit_color2, group=self.groups[4])
							self.visible_exits[name] = (vl1, vl2)
				else:
					if self.spacer == 0:
						name += "-"
						if exit is None:
							color = exit_color2
						elif exit.to == "undefined":
							color = Color(0, 0, 255, 255)
						elif exit.to == "death":
							color = Color (255, 0, 0, 255)
						else:
							color = Color (0, 255, 0, 255)
						a, b, c, d = self.square_from_cp(cp, _d)
						if direction == "west":
							s = (a, b)
						elif direction == "north":
							s = (b, c)
						elif direction == "east":
							s = (c, d)
						elif direction == "south":
							s = (d, a)
						if name in self.visible_exits:
							vl = self.visible_exits[name]
							vl.vertices = self.fat_segment_vertices(s[0], s[1], self.size / radius / 2.0)
							vl.colors = color * (len(vl.colors) // 4)
						else:
							self.visible_exits[name] = self.draw_fat_segment(s[0], s[1], self.size / radius, color, group=self.groups[4])
					else:
						if self.world.isExitLogical(exit):
							l = (self.size * self.spacer_as_float) / 2
							a = cp + (dv * _d)
							b = a + (dv * l)
							if name in self.visible_exits:
								vl = self.visible_exits[name]
								vs = self.fat_segment_vertices(a, b, self.size / radius)
								vl.vertices = vs
							else:
								self.visible_exits[name] = self.draw_fat_segment(a, b, self.size / radius, exit_color1, group=self.groups[4])
						elif exit.to in ("undefined", "death"):
							l = (self.size * 0.75)
							new_cp = cp + dv * l
							if name in self.visible_exits:
								vl = self.visible_exits[name]
								vl.x, vl.y = new_cp
							elif exit.to == "undefined":
								self.visible_exits[name] = pyglet.text.Label("?", font_name="Times New Roman", font_size=(self.size / 100.0) * 72, x=new_cp.x, y=new_cp.y, anchor_x="center", anchor_y="center", color=exit_color1, batch=self.batch, group=self.groups[4])
							else: # Death
								self.visible_exits[name] = pyglet.text.Label("X", font_name="Times New Roman", font_size=(self.size / 100.0) * 72, x=new_cp.x, y=new_cp.y, anchor_x="center", anchor_y="center", color=Color(255,0,0,255), batch=self.batch, group=self.groups[4])
						else: # one-way, random, etc.
							color = exit_color1
							l = (self.size * self.spacer_as_float) / 2
							a = cp + (dv * _d)
							d = a + (dv * l)
							r = ((self.size / radius) / 2.0) * self.spacer_as_float
							if name in self.visible_exits:
								vl1, vl2 = self.visible_exits[name]
								vs1, vs2 = self.arrow_vertices(a, d, r)
								vl1.vertices = vs1
								vl1.colors = color * (len(vl1.colors) // 4)
								vl2.vertices = vs2
								vl2.colors = color * (len(vl2.colors) // 4)
							else:
								self.visible_exits[name] = self.draw_arrow(a, d, r, color, group=self.groups[4])
				newexits.add(name)
		for dead in set(self.visible_exits) - newexits:
			try:
				try:
					self.visible_exits[dead].delete()
				except AttributeError:
					for d in self.visible_exits[dead]:
						d.delete()
			except AssertionError:
				pass
			del self.visible_exits[dead]

	def enable_current_room_markers(self):
		if 'current_room_markers' in self.blinkers:
			return
		current_room_markers = []
		current_room_markers.append(Blinker(self.blink_rate, self.draw_circle, lambda :((self.cp - (self.size / 2.0), (self.size / 100.0) * self.current_room_mark_radius, self.current_room_mark_color), {"group": self.groups[5]})))
		current_room_markers.append(Blinker(self.blink_rate, self.draw_circle, lambda :((self.cp - (self.size / 2.0, -self.size / 2.0), (self.size / 100.0) * self.current_room_mark_radius, self.current_room_mark_color), {"group": self.groups[5]})))
		current_room_markers.append(Blinker(self.blink_rate, self.draw_circle, lambda :((self.cp + (self.size / 2.0), (self.size / 100.0) * self.current_room_mark_radius, self.current_room_mark_color), {"group": self.groups[5]})))
		current_room_markers.append(Blinker(self.blink_rate, self.draw_circle, lambda :((self.cp + (self.size / 2.0, -self.size / 2.0), (self.size / 100.0) * self.current_room_mark_radius, self.current_room_mark_color), {"group": self.groups[5]})))
		self.blinkers['current_room_markers'] = tuple(current_room_markers)

	def redraw(self):
		logger.debug("Redrawing...")
		self.draw_rooms()
		self.draw_exits()


Window.register_event_type('on_map_sync')
