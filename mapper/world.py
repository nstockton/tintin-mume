# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import gc
import heapq
import itertools
import operator
try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import re
import threading
from fuzzywuzzy import fuzz

from . import roomdata
from .utils import regexFuzzy


DIRECTIONS = ["north", "east", "south", "west", "up", "down"]
DIRECTION_COORDINATES = {
	"north": (0, 1, 0),
	"south": (0, -1, 0),
	"west": (-1, 0, 0),
	"east": (1, 0, 0),
	"up": (0, 0, 1),
	"down": (0, 0, -1)
}
LEAD_BEFORE_ENTERING_VNUMS = [
	"196",
	"3473",
	"3474",
	"12138",
	"12637"
]
LIGHT_SYMBOLS = {
	"@": "lit",
	"*": "lit",
	"!": "undefined",
	")": "lit",
	"o": "dark"
}
REVERSE_DIRECTIONS = {
	"north": "south",
	"south": "north",
	"east": "west",
	"west": "east",
	"up": "down",
	"down": "up"
}
RUN_DESTINATION_REGEX = re.compile(r"^(?P<destination>.+?)(?:\s+(?P<flags>\S+))?$")
TERRAIN_SYMBOLS = {
	":": "brush",
	"O": "cavern",
	"#": "city",
	"!": "deathtrap",
	".": "field",
	"f": "forest",
	"(": "hills",
	"[": "indoors",
	"<": "mountains",
	"W": "rapids",
	"+": "road",
	"%": "shallow",
	"=": "tunnel",
	"?": "undefined",
	"U": "underwater",
	"~": "water"
}


class World(object):
	def __init__(self, interface="text"):
		self.isSynced = False
		self.rooms = {}
		self.labels = {}
		self._interface = interface
		if interface != "text":
			self._gui_queue = Queue()
			self._gui_queue_lock = threading.RLock()
			if interface == "hc":
				from .gui.hc import Window
			elif interface == "sighted":
				from .gui.sighted import Window
			self.window = Window(self)
		self._currentRoom = None
		self.loadRooms()
		self.loadLabels()

	@property
	def currentRoom(self):
		return self._currentRoom

	@currentRoom.setter
	def currentRoom(self, value):
		self._currentRoom = value
		if self._interface != "text":
			with self._gui_queue_lock:
				self._gui_queue.put(("on_map_sync", value))

	@currentRoom.deleter
	def currentRoom(self):
		del self._currentRoom

	def GUIRefresh(self):
		"""Trigger the clearing and redrawing of rooms by the GUI"""
		if self._interface != "text":
			with self._gui_queue_lock:
				self._gui_queue.put(("on_gui_refresh",))

	def output(self, text):
		print(text)
		return None

	def loadRooms(self):
		if gc.isenabled():
			gc.disable()
		self.output("Loading the database file.")
		errors, db = roomdata.database.loadRooms()
		if db is None:
			return self.output(errors)
		self.output("Creating room objects.")
		terrainReplacements = {
			"random": "undefined",
			"death": "deathtrap",
			"shallowwater": "shallow"
		}
		mobFlagReplacements = {
			"any": "passive_mob",
			"smob": "aggressive_mob",
			"quest": "quest_mob",
			"scoutguild": "scout_guild",
			"mageguild": "mage_guild",
			"clericguild": "cleric_guild",
			"warriorguild": "warrior_guild",
			"rangerguild": "ranger_guild",
			"armourshop": "armour_shop",
			"foodshop": "food_shop",
			"petshop": "pet_shop",
			"weaponshop": "weapon_shop"
		}
		loadFlagReplacements = {
			"packhorse": "pack_horse",
			"trainedhorse": "trained_horse"
		}
		doorFlagReplacements = {
			"noblock": "no_block",
			"nobreak": "no_break",
			"nopick": "no_pick",
			"needkey": "need_key"
		}
		for vnum, roomDict in db.items():
			newRoom = roomdata.objects.Room(vnum)
			newRoom.name = roomDict["name"]
			newRoom.desc = roomDict["desc"]
			newRoom.dynamicDesc = roomDict["dynamicDesc"]
			newRoom.note = roomDict["note"]
			terrain = roomDict["terrain"]
			newRoom.terrain = terrain if terrain not in terrainReplacements else terrainReplacements[terrain]
			newRoom.light = roomDict["light"]
			newRoom.align = roomDict["align"]
			newRoom.portable = roomDict["portable"]
			newRoom.ridable = roomDict["ridable"]
			try:
				newRoom.avoid = roomDict["avoid"]
			except KeyError:
				pass
			newRoom.mobFlags = {mobFlagReplacements.get(flag, flag) for flag in roomDict["mobFlags"]}
			newRoom.loadFlags = {loadFlagReplacements.get(flag, flag) for flag in roomDict["loadFlags"]}
			newRoom.x = roomDict["x"]
			newRoom.y = roomDict["y"]
			newRoom.z = roomDict["z"]
			newRoom.calculateCost()
			for direction, exitDict in roomDict["exits"].items():
				newExit = self.getNewExit(direction, exitDict["to"], vnum)
				newExit.exitFlags = set(exitDict["exitFlags"])
				newExit.doorFlags = {doorFlagReplacements.get(flag, flag) for flag in exitDict["doorFlags"]}
				newExit.door = exitDict["door"]
				newRoom.exits[direction] = newExit
			self.rooms[vnum] = newRoom
			roomDict.clear()
			del roomDict
		self.currentRoom = self.rooms["0"]
		self.emulationRoom = self.rooms["0"]
		self.lastEmulatedJump = None
		if not gc.isenabled():
			gc.enable()
			gc.collect()
		self.output("Map database loaded.")

	def saveRooms(self):
		if gc.isenabled():
			gc.disable()
		self.output("Creating dict from room objects.")
		db = {}
		for vnum, roomObj in self.rooms.items():
			newRoom = {}
			newRoom["name"] = roomObj.name
			newRoom["desc"] = roomObj.desc
			newRoom["dynamicDesc"] = roomObj.dynamicDesc
			newRoom["note"] = roomObj.note
			newRoom["terrain"] = roomObj.terrain
			newRoom["light"] = roomObj.light
			newRoom["align"] = roomObj.align
			newRoom["portable"] = roomObj.portable
			newRoom["ridable"] = roomObj.ridable
			newRoom["avoid"] = roomObj.avoid
			newRoom["mobFlags"] = sorted(roomObj.mobFlags)
			newRoom["loadFlags"] = sorted(roomObj.loadFlags)
			newRoom["x"] = roomObj.x
			newRoom["y"] = roomObj.y
			newRoom["z"] = roomObj.z
			newRoom["exits"] = {}
			for direction, exitObj in roomObj.exits.items():
				newExit = {}
				newExit["exitFlags"] = sorted(exitObj.exitFlags)
				newExit["doorFlags"] = sorted(exitObj.doorFlags)
				newExit["door"] = exitObj.door
				newExit["to"] = exitObj.to
				newRoom["exits"][direction] = newExit
			db[vnum] = newRoom
		self.output("Saving the database.")
		roomdata.database.dumpRooms(db)
		if not gc.isenabled():
			gc.enable()
			gc.collect()
		self.output("Map Database saved.")

	def loadLabels(self):
		errors, labels = roomdata.database.loadLabels()
		if labels is None:
			return self.output(errors)
		self.labels.update(labels)
		orphans = [label for label, vnum in self.labels.items() if vnum not in self.rooms]
		for label in orphans:
			del self.labels[label]

	def saveLabels(self):
		roomdata.database.dumpLabels(self.labels)

	def getNewExit(self, direction, to="undefined", parent=None):
		newExit = roomdata.objects.Exit()
		newExit.direction = direction
		newExit.to = to
		newExit.vnum = self.currentRoom.vnum if parent is None else parent
		return newExit

	def sortExits(self, exitsDict):
		return sorted(
			exitsDict.items(),
			key=lambda direction: (
				DIRECTIONS.index(direction[0]) if direction[0] in DIRECTIONS else len(DIRECTIONS)
			)
		)

	def isBidirectional(self, exitObj):
		"""
		Returns True if an exit is bidirectional, False if unidirectional.
		I.E. True if moving in a given direction then moving back in the direction
		you just came from would put you back where you started, False otherwise.
		"""
		try:
			dest = self.rooms[exitObj.to]
		except KeyError:
			return False
		revdir = REVERSE_DIRECTIONS[exitObj.direction]
		if revdir in dest.exits and dest.exits[revdir].to == exitObj.vnum:
			return True
		else:
			return False

	def getNeighborsFromCoordinates(self, start=None, radius=1):
		"""A generator which yields all rooms in the vicinity of the given X-Y-Z coordinates.
		Each yielded result contains the vnum, room object reference, and difference in X-Y-Z coordinates."""
		try:
			iter(start)
		except TypeError:
			x = y = z = 0
		else:
			x, y, z = start
		try:
			iter(radius)
		except TypeError:
			radiusX = radiusY = radiusZ = int(radius)
		else:
			radiusX, radiusY, radiusZ = radius
		for vnum, obj in self.rooms.items():
			if obj.x == x and obj.y == y and obj.z == z:
				continue
			differenceX, differenceY, differenceZ = obj.x - x, obj.y - y, obj.z - z
			if abs(differenceX) <= radiusX and abs(differenceY) <= radiusY and abs(differenceZ) <= radiusZ:
				yield(vnum, obj, differenceX, differenceY, differenceZ)

	def getNeighborsFromRoom(self, start=None, radius=1):
		"""A generator which yields all rooms in the vicinity of a room object.
		Each yielded result contains the vnum, room object reference, and difference in X-Y-Z coordinates."""
		if start is None:
			start = self.currentRoom
		x, y, z = start.x, start.y, start.z
		try:
			iter(radius)
		except TypeError:
			radiusX = radiusY = radiusZ = int(radius)
		else:
			radiusX, radiusY, radiusZ = radius
		for vnum, obj in self.rooms.items():
			differenceX, differenceY, differenceZ = obj.x - x, obj.y - y, obj.z - z
			if (
				abs(differenceX) <= radiusX
				and abs(differenceY) <= radiusY
				and abs(differenceZ) <= radiusZ
				and obj is not start
			):
				yield(vnum, obj, differenceX, differenceY, differenceZ)

	def getVnum(self, roomObj=None):
		result = None
		if roomObj is None:
			roomObj = self.currentRoom
		for vnum, obj in self.rooms.items():
			if obj is roomObj:
				result = vnum
				break
		return result

	def coordinatesSubtract(self, first, second):
		return tuple(map(operator.sub, first, second))

	def coordinatesAdd(self, first, second):
		return tuple(map(operator.add, first, second))

	def coordinatesAddDirection(self, first, second):
		if first in DIRECTIONS:
			first = DIRECTION_COORDINATES[first]
		if second in DIRECTIONS:
			second = DIRECTION_COORDINATES[second]
		return self.coordinatesAdd(first, second)

	def getNewVnum(self):
		return str(max(int(i) for i in self.rooms) + 1)

	def revnum(self, *args):
		if not args or not args[0]:
			match = None
		else:
			match = re.match(r"^(?:(?P<origin>\d+)\s+)?(?:\s*(?P<destination>\d+)\s*)$", args[0].strip().lower())
		if not match:
			self.output("Syntax: 'revnum [Origin VNum] [Destination VNum]'.")
			return None
		else:
			matchDict = match.groupdict()
		if not matchDict["destination"]:
			self.output("Error: you need to supply a destination VNum.")
			return None
		destination = matchDict["destination"]
		if not matchDict["origin"]:
			origin = self.currentRoom.vnum
			self.output("Changing the VNum of the current room to '{}'.".format(destination))
		else:
			origin = matchDict["origin"]
			self.output("Changing the Vnum '{}' to '{}'.".format(origin, destination))
		for roomVnum, roomObj in self.rooms.items():
			for direction, exitObj in roomObj.exits.items():
				if roomVnum == origin:
					exitObj.vnum = destination
				if exitObj.to == origin:
					self.rooms[roomVnum].exits[direction].to = destination
		self.rooms[origin].vnum = destination
		self.rooms[destination] = self.rooms[origin]
		del self.rooms[origin]

	def rdelete(self, *args):
		if args and args[0] is not None and args[0].strip().isdigit():
			if args[0].strip() in self.rooms:
				vnum = args[0].strip()
			else:
				return "Error: the vnum '{}' does not exist.".format(args[0].strip())
		elif self.isSynced:
			vnum = self.currentRoom.vnum
			self.isSynced = False
			self.currentRoom = self.rooms["0"]
		else:
			return "Syntax: rdelete [vnum]"
		output = "Deleting room '{}' with name '{}'.".format(vnum, self.rooms[vnum].name)
		for roomVnum, roomObj in self.rooms.items():
			for direction, exitObj in roomObj.exits.items():
				if exitObj.to == vnum:
					self.rooms[roomVnum].exits[direction].to = "undefined"
		del self.rooms[vnum]
		self.GUIRefresh()
		return output

	def searchRooms(self, *args, **kwArgs):
		exactMatch = bool(kwArgs.get("exactMatch"))
		validArgs = (
			"name",
			"desc",
			"dynamicDesc",
			"note",
			"terrain",
			"light",
			"align",
			"portable",
			"ridable",
			"x",
			"y",
			"z",
			"mobFlags",
			"loadFlags",
			"exitFlags",
			"doorFlags",
			"to",
			"door"
		)
		kwArgs = {
			key: value.strip().lower() for key, value in kwArgs.items()
			if key.strip() in validArgs and value.strip()
		}
		results = []
		if not kwArgs:
			return results
		for vnum, roomObj in self.rooms.items():
			keysMatched = 0
			for key, value in kwArgs.items():
				if key in ("name", "desc", "dynamicDesc", "note"):
					roomData = getattr(roomObj, key, "").strip().lower()
					if not exactMatch and value in roomData or roomData == value:
						keysMatched += 1
				elif (
					key in ("terrain", "light", "align", "portable", "ridable", "x", "y", "z")
					and getattr(roomObj, key, "").strip().lower() == value
				):
					keysMatched += 1
				elif key in ("mobFlags", "loadFlags") and getattr(roomObj, key, set()).intersection(value):
					keysMatched += 1
			for direction, exitObj in roomObj.exits.items():
				for key, value in kwArgs.items():
					if key in ("exitFlags", "doorFlags") and getattr(exitObj, key, set()).intersection(value):
						keysMatched += 1
					elif key in ("to", "door") and getattr(exitObj, key, "").strip().lower() == value:
						keysMatched += 1
			if len(kwArgs) == keysMatched:
				results.append(roomObj)
		return results

	def fdoor(self, findFormat, *args):
		if not args or args[0] is None or not args[0].strip():
			return "Usage: 'fdoor [text]'."
		results = self.searchRooms(door=args[0])
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=", ".join(
					exitDir + ": " + exitObj.door for exitDir, exitObj in roomObj.exits.items()
					if args[0].strip() in exitObj.door
				),
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**vars(roomObj)
			) for roomObj in reversed(results[:20])
		)

	def fdynamic(self, findFormat, *args):
		if not args or args[0] is None or not args[0].strip():
			return "Usage: 'fdynamic [text]'."
		results = self.searchRooms(dynamicDesc=args[0])
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=roomObj.dynamicDesc,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**vars(roomObj)
			) for roomObj in reversed(results[:20])
		)

	def flabel(self, findFormat, *args):
		if not self.labels:
			return "No labels defined."
		if not args or args[0] is None or not args[0].strip():
			text = ""
		else:
			text = args[0].strip().lower()
		results = {
			self.rooms[vnum] for label, vnum in self.labels.items()
			if text and text in label.strip().lower() or not text
		}
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		return "\n".join(
			findFormat.format(
				attribute=self.getlabel(roomObj.vnum),
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**vars(roomObj)
			) for roomObj in reversed(sorted(results, key=lambda r: r.manhattanDistance(currentRoom))[:20])
		)

	def fname(self, findFormat, *args):
		if not args or args[0] is None or not args[0].strip():
			return "Usage: 'fname [text]'."
		results = self.searchRooms(name=args[0])
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute="" if "{name}" in findFormat and "{attribute}" in findFormat else roomObj.name,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**vars(roomObj)
			) for roomObj in reversed(results[:20])
		)

	def fnote(self, findFormat, *args):
		if not args or args[0] is None or not args[0].strip():
			return "Usage: 'fnote [text]'."
		results = self.searchRooms(note=args[0])
		if not results:
			return "Nothing found."
		currentRoom = self.currentRoom
		results.sort(key=lambda roomObj: roomObj.manhattanDistance(currentRoom))
		return "\n".join(
			findFormat.format(
				attribute=roomObj.note,
				direction=currentRoom.directionTo(roomObj),
				clockPosition=currentRoom.clockPositionTo(roomObj),
				distance=currentRoom.manhattanDistance(roomObj),
				**vars(roomObj)
			) for roomObj in reversed(results[:20])
		)

	def rnote(self, *args):
		if not args or args[0] is None or not args[0].strip():
			return (
				"Room note set to '{}'. Use 'rnote [text]' to change it, "
				+ "'rnote -a [text]' to append to it, or 'rnote -r' to remove it."
			).format(self.currentRoom.note)
		note = args[0].strip()
		if note.lower().startswith("-r"):
			if len(note) > 2:
				return "Error: '-r' requires no extra arguments. Change aborted."
			self.currentRoom.note = ""
			return "Note removed."
		elif note.lower().startswith("-a"):
			if len(note) == 2:
				return "Error: '-a' requires text to be appended. Change aborted."
			self.currentRoom.note = "{} {}".format(self.currentRoom.note.strip(), note[2:].strip())
		else:
			self.currentRoom.note = note
		return "Room note now set to '{}'.".format(self.currentRoom.note)

	def ralign(self, *args):
		validValues = ("good", "neutral", "evil", "undefined")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return (
				"Room alignment set to '{}'. Use 'ralign [{}]' to change it."
			).format(self.currentRoom.align, " | ".join(validValues))
		self.currentRoom.align = args[0].strip().lower()
		return "Setting room align to '{}'.".format(self.currentRoom.align)

	def rlight(self, *args):
		if (
			not args
			or not args[0]
			or args[0].strip() not in LIGHT_SYMBOLS
			and args[0].strip().lower() not in LIGHT_SYMBOLS.values()
		):
			return (
				"Room light set to '{}'. Use 'rlight [{}]' to change it."
			).format(self.currentRoom.light, " | ".join(set(LIGHT_SYMBOLS.values())))
		try:
			self.currentRoom.light = LIGHT_SYMBOLS[args[0].strip()]
		except KeyError:
			self.currentRoom.light = args[0].strip().lower()
		return "Setting room light to '{}'.".format(self.currentRoom.light)

	def rportable(self, *args):
		validValues = ("portable", "notportable", "undefined")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return (
				"Room portable set to '{}'. Use 'rportable [{}]' to change it."
			).format(self.currentRoom.portable, " | ".join(validValues))
		self.currentRoom.portable = args[0].strip().lower()
		return "Setting room portable to '{}'.".format(self.currentRoom.portable)

	def rridable(self, *args):
		validValues = ("ridable", "notridable", "undefined")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return (
				"Room ridable set to '{}'. Use 'rridable [{}]' to change it."
			).format(self.currentRoom.ridable, " | ".join(validValues))
		self.currentRoom.ridable = args[0].strip().lower()
		self.currentRoom.calculateCost()
		return "Setting room ridable to '{}'.".format(self.currentRoom.ridable)

	def ravoid(self, *args):
		validValues = ("+", "-")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return (
				"Room avoid {}. Use 'ravoid [{}]' to change it."
			).format("enabled" if self.currentRoom.avoid else "disabled", " | ".join(validValues))
		self.currentRoom.avoid = args[0].strip() == "+"
		self.currentRoom.calculateCost()
		return "{} room avoid.".format("Enabling" if self.currentRoom.avoid else "Disabling")

	def rterrain(self, *args):
		if (
			not args
			or not args[0]
			or args[0].strip() not in TERRAIN_SYMBOLS
			and args[0].strip().lower() not in TERRAIN_SYMBOLS.values()
		):
			return (
				"Room terrain set to '{}'. Use 'rterrain [{}]' to change it."
			).format(self.currentRoom.terrain, " | ".join(sorted(TERRAIN_SYMBOLS.values())))
		try:
			self.currentRoom.terrain = TERRAIN_SYMBOLS[args[0].strip()]
		except KeyError:
			self.currentRoom.terrain = args[0].strip().lower()
		self.currentRoom.calculateCost()
		self.GUIRefresh()
		return "Setting room terrain to '{}'.".format(self.currentRoom.terrain)

	def rx(self, *args):
		if args and args[0] and args[0].strip():
			try:
				self.currentRoom.x = int(args[0].strip())
				self.GUIRefresh()
				return "Setting room X coordinate to '{}'.".format(self.currentRoom.x)
			except ValueError:
				return "Error: room coordinates must be comprised of digits only."
		return "Room coordinate X set to '{}'. Use 'rx [digit]' to change it.".format(self.currentRoom.x)

	def ry(self, *args):
		if args and args[0] and args[0].strip():
			try:
				self.currentRoom.y = int(args[0].strip())
				self.GUIRefresh()
				return "Setting room Y coordinate to '{}'.".format(self.currentRoom.y)
			except ValueError:
				return "Error: room coordinates must be comprised of digits only."
		return "Room coordinate Y set to '{}'. Use 'ry [digit]' to change it.".format(self.currentRoom.y)

	def rz(self, *args):
		if args and args[0] and args[0].strip():
			try:
				self.currentRoom.z = int(args[0].strip())
				self.GUIRefresh()
				return "Setting room Z coordinate to '{}'.".format(self.currentRoom.z)
			except ValueError:
				return "Error: room coordinates must be comprised of digits only."
		return "Room coordinate Z set to '{}'. Use 'rz [digit]' to change it.".format(self.currentRoom.z)

	def rmobflags(self, *args):
		regex = re.compile(
			r"^(?P<mode>{}|{})\s+(?P<flag>{})".format(
				regexFuzzy("add"),
				regexFuzzy("remove"),
				"|".join(roomdata.objects.VALID_MOB_FLAGS)
			)
		)
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return (
				"Mob flags set to '{}'. Use 'rmobflags [add | remove] [{}]' to change them."
			).format(", ".join(self.currentRoom.mobFlags), " | ".join(roomdata.objects.VALID_MOB_FLAGS))
		if "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.mobFlags:
				self.currentRoom.mobFlags.remove(matchDict["flag"])
				return "Mob flag '{}' removed.".format(matchDict["flag"])
			else:
				return "Mob flag '{}' not set.".format(matchDict["flag"])
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.mobFlags:
				return "Mob flag '{}' already set.".format(matchDict["flag"])
			else:
				self.currentRoom.mobFlags.add(matchDict["flag"])
				return "Mob flag '{}' added.".format(matchDict["flag"])

	def rloadflags(self, *args):
		regex = re.compile(
			r"^(?P<mode>{}|{})\s+(?P<flag>{})".format(
				regexFuzzy("add"),
				regexFuzzy("remove"),
				"|".join(roomdata.objects.VALID_LOAD_FLAGS)
			)
		)
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return (
				"Load flags set to '{}'. Use 'rloadflags [add | remove] [{}]' to change them."
			).format(", ".join(self.currentRoom.loadFlags), " | ".join(roomdata.objects.VALID_LOAD_FLAGS))
		if "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.loadFlags:
				self.currentRoom.loadFlags.remove(matchDict["flag"])
				return "Load flag '{}' removed.".format(matchDict["flag"])
			else:
				return "Load flag '{}' not set.".format(matchDict["flag"])
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.loadFlags:
				return "Load flag '{}' already set.".format(matchDict["flag"])
			else:
				self.currentRoom.loadFlags.add(matchDict["flag"])
				return "Load flag '{}' added.".format(matchDict["flag"])

	def exitflags(self, *args):
		regex = re.compile(
			r"^((?P<mode>{}|{})\s+)?((?P<flag>{})\s+)?(?P<direction>{})".format(
				regexFuzzy("add"),
				regexFuzzy("remove"),
				"|".join(roomdata.objects.VALID_EXIT_FLAGS),
				regexFuzzy(DIRECTIONS)
			)
		)
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return (
				"Syntax: 'exitflags [add | remove] [{}] [{}]'."
			).format(" | ".join(roomdata.objects.VALID_EXIT_FLAGS), " | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if direction not in self.currentRoom.exits:
			return "Exit {} does not exist.".format(direction)
		elif not matchDict["mode"]:
			return (
				"Exit flags '{}' set to '{}'."
			).format(direction, ", ".join(self.currentRoom.exits[direction].exitFlags))
		elif "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].exitFlags:
				self.currentRoom.exits[direction].exitFlags.remove(matchDict["flag"])
				return "Exit flag '{}' in direction '{}' removed.".format(matchDict["flag"], direction)
			else:
				return "Exit flag '{}' in direction '{}' not set.".format(matchDict["flag"], direction)
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].exitFlags:
				return "Exit flag '{}' in direction '{}' already set.".format(matchDict["flag"], direction)
			else:
				self.currentRoom.exits[direction].exitFlags.add(matchDict["flag"])
				return "Exit flag '{}' in direction '{}' added.".format(matchDict["flag"], direction)

	def doorflags(self, *args):
		regex = re.compile(
			r"^((?P<mode>{}|{})\s+)?((?P<flag>{})\s+)?(?P<direction>{})".format(
				regexFuzzy("add"),
				regexFuzzy("remove"),
				"|".join(roomdata.objects.VALID_DOOR_FLAGS),
				regexFuzzy(DIRECTIONS)
			)
		)
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return (
				"Syntax: 'doorflags [add | remove] [{}] [{}]'."
			).format(" | ".join(roomdata.objects.VALID_DOOR_FLAGS), " | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if direction not in self.currentRoom.exits:
			return "Exit {} does not exist.".format(direction)
		elif not matchDict["mode"]:
			return (
				"Door flags '{}' set to '{}'."
			).format(direction, ", ".join(self.currentRoom.exits[direction].doorFlags))
		elif "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].doorFlags:
				self.currentRoom.exits[direction].doorFlags.remove(matchDict["flag"])
				return "Door flag '{}' in direction '{}' removed.".format(matchDict["flag"], direction)
			else:
				return "Door flag '{}' in direction '{}' not set.".format(matchDict["flag"], direction)
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].doorFlags:
				return "Door flag '{}' in direction '{}' already set.".format(matchDict["flag"], direction)
			else:
				self.currentRoom.exits[direction].doorFlags.add(matchDict["flag"])
				return "Door flag '{}' in direction '{}' added.".format(matchDict["flag"], direction)

	def secret(self, *args):
		regex = re.compile(
			r"^((?P<mode>{}|{})\s+)?((?P<name>[A-Za-z]+)\s+)?(?P<direction>{})".format(
				regexFuzzy("add"),
				regexFuzzy("remove"),
				regexFuzzy(DIRECTIONS)
			)
		)
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Syntax: 'secret [add | remove] [name] [{}]'.".format(" | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if matchDict["mode"] and "add".startswith(matchDict["mode"]):
			if not matchDict["name"]:
				return "Error: 'add' expects a name for the secret."
			elif direction not in self.currentRoom.exits:
				self.currentRoom.exits[direction] = self.getNewExit(direction)
			self.currentRoom.exits[direction].exitFlags.add("door")
			self.currentRoom.exits[direction].doorFlags.add("hidden")
			self.currentRoom.exits[direction].door = matchDict["name"]
			self.GUIRefresh()
			return "Adding secret '{}' to direction '{}'.".format(matchDict["name"], direction)
		elif direction not in self.currentRoom.exits:
			return "Exit {} does not exist.".format(direction)
		elif not self.currentRoom.exits[direction].door:
			return "No secret {} of here.".format(direction)
		elif not matchDict["mode"]:
			return "Exit '{}' has secret '{}'.".format(direction, self.currentRoom.exits[direction].door)
		elif "remove".startswith(matchDict["mode"]):
			if "hidden" in self.currentRoom.exits[direction].doorFlags:
				self.currentRoom.exits[direction].doorFlags.remove("hidden")
			self.currentRoom.exits[direction].door = ""
			self.GUIRefresh()
			return "Secret {} removed.".format(direction)

	def rlink(self, *args):
		regex = re.compile(
			r"^((?P<mode>{}|{})\s+)?((?P<oneway>{})\s+)?"
			r"((?P<vnum>\d+|undefined)\s+)?(?P<direction>{})".format(
				regexFuzzy("add"),
				regexFuzzy("remove"),
				regexFuzzy("oneway"),
				regexFuzzy(DIRECTIONS)
			)
		)
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Syntax: 'rlink [add | remove] [oneway] [vnum] [{}]'.".format(" | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if matchDict["mode"] and "add".startswith(matchDict["mode"]):
			reversedDirection = REVERSE_DIRECTIONS[direction]
			if not matchDict["vnum"]:
				return "Error: 'add' expects a vnum or 'undefined'."
			elif matchDict["vnum"] != "undefined" and matchDict["vnum"] not in self.rooms:
				return "Error: vnum {} not in database.".format(matchDict["vnum"])
			elif direction not in self.currentRoom.exits:
				self.currentRoom.exits[direction] = self.getNewExit(direction)
			self.currentRoom.exits[direction].to = matchDict["vnum"]
			if matchDict["vnum"] == "undefined":
				self.GUIRefresh()
				return "Direction {} now undefined.".format(direction)
			elif not matchDict["oneway"]:
				if (
					reversedDirection not in self.rooms[matchDict["vnum"]].exits
					or self.rooms[matchDict["vnum"]].exits[reversedDirection].to == "undefined"
				):
					self.rooms[matchDict["vnum"]].exits[reversedDirection] = self.getNewExit(
						reversedDirection,
						self.currentRoom.vnum
					)
					self.GUIRefresh()
					return (
						"Linking direction {} to {} with name '{}'.\n"
						"Linked exit {} in second room with this room.".format(
							direction,
							matchDict["vnum"],
							self.rooms[matchDict["vnum"]].name if matchDict["vnum"] in self.rooms else "",
							reversedDirection
						)
					)
				else:
					self.GUIRefresh()
					return (
						"Linking direction {} to {} with name '{}'.\n"
						"Unable to link exit {} in second room with this room: exit already defined.".format(
							direction,
							matchDict["vnum"],
							self.rooms[matchDict["vnum"]].name if matchDict["vnum"] in self.rooms else "",
							reversedDirection
						)
					)
			else:
				self.GUIRefresh()
				return (
					"Linking direction {} one way to {} with name '{}'.".format(
						direction,
						matchDict["vnum"],
						self.rooms[matchDict["vnum"]].name if matchDict["vnum"] in self.rooms else ""
					)
				)
		elif direction not in self.currentRoom.exits:
			return "Exit {} does not exist.".format(direction)
		elif not matchDict["mode"]:
			return "Exit '{}' links to '{}' with name '{}'.".format(
				direction,
				self.currentRoom.exits[direction].to,
				(
					self.rooms[self.currentRoom.exits[direction].to].name
					if self.currentRoom.exits[direction].to in self.rooms
					else ""
				)
			)
		elif "remove".startswith(matchDict["mode"]):
			del self.currentRoom.exits[direction]
			self.GUIRefresh()
			return "Exit {} removed.".format(direction)

	def getlabel(self, *args):
		if not args or not args[0] or not args[0].strip().isdigit():
			findVnum = self.currentRoom.vnum
		else:
			findVnum = args[0].strip()
		result = ", ".join(sorted(label for label, vnum in self.labels.items() if vnum == findVnum))
		if result:
			return "Room labels: {}".format(result)
		else:
			return "Room not labeled."

	def rlabel(self, *args):
		if not args or not args[0]:
			match = None
		else:
			match = re.match(
				r"^(?P<action>add|delete|info|search)(?:\s+(?P<label>\S+))?(?:\s+(?P<vnum>\d+))?$",
				args[0].strip().lower()
			)
		if not match:
			self.output(
				"Syntax: 'rlabel [add|info|delete] [label] [vnum]'. Vnum is only used when adding a room. "
				+ "Leave it blank to use the current room's vnum. Use '_label info all' to get a list of all labels."
			)
			return None
		else:
			matchDict = match.groupdict()
		if not matchDict["label"]:
			self.output("Error: you need to supply a label.")
			return None
		label = matchDict["label"]
		if label.isdecimal():
			self.output("labels cannot be decimal values.")
			return None
		if matchDict["action"] == "add":
			if not matchDict["vnum"]:
				vnum = self.currentRoom.vnum
				self.output("adding the label '{0}' to current room with VNum '{1}'.".format(label, vnum))
			else:
				vnum = matchDict["vnum"]
				self.output("adding the label '{0}' with VNum '{1}'.".format(label, vnum))
			self.labels[label] = vnum
			self.saveLabels()
		elif matchDict["action"] == "delete":
			if label not in self.labels:
				self.output("There aren't any labels matching '{0}' in the database.".format(label))
				return None
			self.output("Deleting label '{0}'.".format(label))
			del self.labels[label]
			self.saveLabels()
		elif matchDict["action"] == "info":
			if "all".startswith(label):
				if self.labels:
					return ["{0} - {1}".format(labelString, vnum) for labelString, vnum in sorted(self.labels.items())]
				else:
					self.output("There aren't any labels in the database yet.")
			elif label not in self.labels:
				self.output("There aren't any labels matching '{0}' in the database.".format(label))
			else:
				self.output("Label '{0}' points to room '{1}'.".format(label, self.labels[label]))
		elif matchDict["action"] == "search":
			results = sorted(
				"{} - {} - {}".format(
					name,
					self.rooms[vnum].name if vnum in self.rooms else "VNum not in map",
					vnum
				) for name, vnum in self.labels.items() if label in name
			)
			if not results:
				self.output("Nothing found.")
			else:
				self.output("\n".join(results))

	def rinfo(self, *args):
		if not args or not args[0]:
			vnum = self.currentRoom.vnum
		else:
			vnum = args[0].strip().lower()
		if vnum in self.labels:
			vnum = self.labels[vnum]
		if vnum in self.rooms:
			room = self.rooms[vnum]
		else:
			return ["Error: No such vnum or label, '{0}'".format(vnum)]
		info = []
		info.append("vnum: '{0}'".format(room.vnum))
		info.append("Name: '{0}'".format(room.name))
		info.append("Description:")
		info.append("-----")
		info.extend(room.desc.splitlines())
		info.append("-----")
		info.append("Dynamic Desc:")
		info.append("-----")
		info.extend(room.dynamicDesc.splitlines())
		info.append("-----")
		info.append("Note: '{0}'".format(room.note))
		info.append("Terrain: '{0}'".format(room.terrain))
		info.append("Cost: '{0}'".format(room.cost))
		info.append("Light: '{0}'".format(room.light))
		info.append("Align: '{0}'".format(room.align))
		info.append("Portable: '{0}'".format(room.portable))
		info.append("Ridable: '{0}'".format(room.ridable))
		info.append("Mob Flags: '{0}'".format(", ".join(room.mobFlags)))
		info.append("Load Flags: '{0}'".format(", ".join(room.loadFlags)))
		info.append("Coordinates (X, Y, Z): '{0}', '{1}', '{2}'".format(room.x, room.y, room.z))
		info.append("Exits:")
		for direction, exitcls in self.sortExits(room.exits):
			info.append("-----")
			info.append("Direction: '{0}'".format(direction))
			info.append("To: '{0}'".format(exitcls.to))
			info.append("Exit Flags: '{0}'".format(", ".join(exitcls.exitFlags)))
			info.append("Door Name: '{0}'".format(exitcls.door))
			info.append("Door Flags: '{0}'".format(", ".join(exitcls.doorFlags)))
		return info

	def createSpeedWalk(self, directionsList):
		"""Given a list of directions, return a string of the directions in standard speed walk format"""
		def compressDirections(directionsBuffer):
			speedWalkDirs = []
			for direction, group in itertools.groupby(directionsBuffer):
				lenGroup = len(list(group))
				if lenGroup == 1:
					speedWalkDirs.append(direction[0])
				else:
					speedWalkDirs.append("{0}{1}".format(lenGroup, direction[0]))
			return speedWalkDirs
		numDirections = len([d for d in directionsList if d in DIRECTIONS])
		result = []
		directionsBuffer = []
		while directionsList:
			item = directionsList.pop()
			if item in DIRECTIONS:
				directionsBuffer.append(item)
			else:
				# The item is not a direction, so process the directions buffer, clear the buffer,
				# and add the resulting list plus the item to the result.
				result.extend(compressDirections(directionsBuffer))
				directionsBuffer = []
				result.append(item)
		# Process any remaining items in the directions buffer.
		if directionsBuffer:
			result.extend(compressDirections(directionsBuffer))
		return "{} rooms. {}".format(numDirections, ", ".join(result))

	def path(self, *args):
		if not args or not args[0]:
			return "Usage: path [label|vnum]"
		match = RUN_DESTINATION_REGEX.match(args[0].strip())
		destination = match.group("destination")
		flags = match.group("flags")
		if flags:
			flags = flags.split("|")
		else:
			flags = None
		result = self.pathFind(destination=destination, flags=flags)
		if result is not None:
			return self.createSpeedWalk(result)

	def pathFind(self, origin=None, destination=None, flags=None):
		"""Find the path"""
		origin = origin or self.currentRoom
		if not origin:
			self.output("Error! The mapper has no location. Please use the sync command then try again.")
		destinationRoom, errorFindingDestination = self.getRoomFromLabel(destination)
		if errorFindingDestination:
			self.output(errorFindingDestination)
			return None
		if origin is destinationRoom:
			self.output("You are already there!")
			return []
		if flags:
			avoidTerrains = frozenset(
				terrain for terrain in roomdata.objects.TERRAIN_COSTS
				if "no{}".format(terrain) in flags
			)
		else:
			avoidTerrains = frozenset()
		ignoreVnums = frozenset(("undefined", "death"))
		isDestinationFunc = lambda currentRoomObj: currentRoomObj is destinationRoom  # NOQA: E731
		exitIgnoreFunc = lambda exitObj: exitObj.to in ignoreVnums  # NOQA: E731
		exitCostFunc = lambda exitObj, neighborRoomObj: (  # NOQA: E731
			(5 if "door" in exitObj.exitFlags or "climb" in exitObj.exitFlags else 0)
			+ (1000 if "avoid" in exitObj.exitFlags else 0)
			+ (10 if neighborRoomObj.terrain in avoidTerrains else 0)
		)
		exitDestinationFunc = None
		return self._pathFind(origin, isDestinationFunc, exitIgnoreFunc, exitCostFunc, exitDestinationFunc)

	def _pathFind(
			self,
			origin,
			isDestinationFunc=None,
			exitIgnoreFunc=None,
			exitCostFunc=None,
			exitDestinationFunc=None
	):
		# Each key-value pare that gets added to this dict will be a parent room and child room respectively.
		parents = {origin: origin}
		# unprocessed rooms.
		opened = []
		# Using a binary heap for storing unvisited rooms significantly increases performance.
		# https://en.wikipedia.org/wiki/Binary_heap
		heapq.heapify(opened)
		# Put the origin cost and origin room on the opened rooms heap to be processed first.
		heapq.heappush(opened, (origin.cost, origin))
		# previously processed rooms.
		closed = {}
		# Ignore the origin from the search by adding it to the closed rooms dict.
		closed[origin] = origin.cost
		# Search while there are rooms left in the opened heap.
		while opened:
			# Pop the last room cost and room object reference off the opened heap for processing.
			currentRoomCost, currentRoomObj = heapq.heappop(opened)
			if isDestinationFunc and isDestinationFunc(currentRoomObj):
				# We successfully found a path from the origin to the destination.
				break
			# Loop through the exits, and process each room linked to the current room.
			for exitDirection, exitObj in currentRoomObj.exits.items():
				if exitIgnoreFunc and exitIgnoreFunc(exitObj):
					continue
				# Get a reference to the room object that the exit leads to using the room's vnum.
				neighborRoomObj = self.rooms[exitObj.to]
				# The neighbor room cost should be the sum of all movement costs
				# to get to the neighbor room from the origin room.
				neighborRoomCost = (
					currentRoomCost
					+ neighborRoomObj.cost
					+ exitCostFunc(exitObj, neighborRoomObj) if exitCostFunc else 0
				)
				# We're only interested in the neighbor room if it hasn't been encountered yet,
				# or if the cost of moving from the current room to the neighbor room is less than
				# the cost of moving to the neighbor room from a previously discovered room.
				if neighborRoomObj not in closed or closed[neighborRoomObj] > neighborRoomCost:
					# Add the room object and room cost to the dict of closed rooms,
					# and put it on the opened rooms heap to be processed.
					closed[neighborRoomObj] = neighborRoomCost
					heapq.heappush(opened, (neighborRoomCost, neighborRoomObj))
					# Since the current room is so far the most optimal way into the neighbor room,
					# set it as the parent of the neighbor room.
					parents[neighborRoomObj] = (currentRoomObj, exitDirection)
					if exitDestinationFunc and exitDestinationFunc(exitObj, neighborRoomObj):
						break
		else:
			# The while loop terminated normally (I.E. without encountering a break statement),
			# and the destination was *not* found.
			self.output("No routes found.")
			return None
		# The while statement was broken prematurely, meaning that the destination was found.
		# Find the path from the origin to the destination by traversing the hierarchy
		# of room parents, starting with the current room.
		results = []
		while currentRoomObj is not origin:
			currentRoomObj, direction = parents[currentRoomObj]
			if (
				currentRoomObj.vnum in LEAD_BEFORE_ENTERING_VNUMS
				and currentRoomObj.exits[direction].to not in LEAD_BEFORE_ENTERING_VNUMS
				and currentRoomObj is not origin
			):
				results.append("ride")
			results.append(direction)
			if (
				currentRoomObj.exits[direction].to in LEAD_BEFORE_ENTERING_VNUMS
				and (currentRoomObj.vnum not in LEAD_BEFORE_ENTERING_VNUMS or currentRoomObj is origin)
			):
				results.append("lead")
			if "door" in currentRoomObj.exits[direction].exitFlags:
				results.append(
					"open {} {}".format(
						(
							currentRoomObj.exits[direction].door
							if currentRoomObj.exits[direction].door
							else "exit"
						),
						direction
					)
				)
		return results

	def getRoomFromLabel(self, label):
		"""Takes a single argument, and returns a tuple of length 2.
		If successful, the first element returned is a room object, and the second element is none.
		Otherwise, the first element returned is None, and the second element is a human-readable error message.
		If the given argument is a room object, it is returned as is.
		If the given argument is a room vnum corresponding to an extant room, the corresponding room is returned.
		If the given argument is the label of a room, that room is returned.
		Otherwise, None is returned with a helpful error message for the user.
		"""
		if isinstance(label, roomdata.objects.Room):
			return label, None
		label = label.strip().lower()
		if not label:
			return None, "No label or room vnum specified."
		elif label.isdecimal():
			vnum = label
			if vnum in self.rooms:
				return self.rooms[vnum], None
			else:
				return None, "No room with vnum " + vnum
		elif label in self.labels:
			vnum = self.labels[label]
			if vnum in self.rooms:
				return self.rooms[vnum], None
			else:
				return None, "{label} is set to vnum {vnum}, but there is no room with that vnum".format(
					label=label,
					vnum=vnum
				)
		else:  # The label is neither a vnum nor an existing label
			similarLabels = list(self.labels)
			similarLabels.sort(reverse=True, key=lambda l: fuzz.ratio(l, label))
			return None, "Unknown label. Did you mean {}?".format(", ".join(similarLabels[0:4]))
