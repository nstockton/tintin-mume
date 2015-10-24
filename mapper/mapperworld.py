# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import codecs
import heapq
import itertools
import json
import os.path
import re

from .mapperconstants import IS_PYTHON_2, DIRECTIONS, MAP_FILE, SAMPLE_MAP_FILE, LABELS_FILE, SAMPLE_LABELS_FILE, AVOID_DYNAMIC_DESC_REGEX, LEAD_BEFORE_ENTERING_VNUMS, TERRAIN_COSTS, TERRAIN_SYMBOLS, LIGHT_SYMBOLS, VALID_MOB_FLAGS, VALID_LOAD_FLAGS, VALID_EXIT_FLAGS, VALID_DOOR_FLAGS, DIRECTION_COORDINATES, REVERSE_DIRECTIONS
from .utils import iterItems, getDirectoryPath, regexFuzzy


class Room(object):
	def __init__(self, vnum):
		self.vnum = vnum
		self.name = ""
		self.desc = ""
		self.dynamicDesc = ""
		self.note = ""
		self.terrain = "undefined"
		self.cost = TERRAIN_COSTS["undefined"]
		self.light = "undefined"
		self.align = "undefined"
		self.portable = "undefined"
		self.ridable = "undefined"
		self.avoid = False
		self.mobFlags = set()
		self.loadFlags = set()
		self.x = 0
		self.y = 0
		self.z = 0
		self.exits = {}

	def __lt__(self, other):
		# Unlike in Python 2 where most objects are sortable by default, our Room class isn't automatically sortable in Python 3.
		# If we don't override this method, the path finder will throw an exception in Python 3 because heapq.heappush requires that any object passed to it be sortable.
		# We'll return False because we want heapq.heappush to sort the tuples of movement cost and room object by the first item in the tuple (room cost), and the order of rooms with the same movement cost is irrelevant.
		return False

	def calculateCost(self):
		try:
			self.cost = TERRAIN_COSTS[self.terrain]
		except KeyError:
			self.cost = TERRAIN_COSTS["undefined"]
		if self.avoid or AVOID_DYNAMIC_DESC_REGEX.search(self.dynamicDesc):
			self.cost += 1000.0
		if self.ridable == "notridable":
			self.cost += 5.0


class Exit(object):
	def __init__(self):
		self.to = "undefined"
		self.exitFlags = set(["exit"])
		self.door = ""
		self.doorFlags = set()


class World(object):
	def __init__(self):
		self.isSynced = False
		self.rooms = {}
		self.labels = {}
		self.currentRoom = None
		self.prevRoom = None
		self.loadRooms()
		self.loadLabels()

	def output(self, text):
		print(text)
		return None

	def loadRooms(self):
		self.output("Loading the JSon database file.")
		mapDirectory = getDirectoryPath("maps")
		mapFile = os.path.join(mapDirectory, MAP_FILE)
		sampleMapFile = os.path.join(mapDirectory, SAMPLE_MAP_FILE)
		if os.path.exists(mapFile):
			if not os.path.isdir(mapFile):
				path = mapFile
			else:
				path = None
				self.output("Error: '{0}' is a directory, not a file.".format(mapFile))
		elif os.path.exists(sampleMapFile):
			if not os.path.isdir(sampleMapFile):
				path = sampleMapFile
			else:
				path = None
				self.output("Error: '{0}' is a directory, not a file.".format(sampleMapFile))
		else:
			return self.output("Error: neither '{0}' nor '{1}' can be found.".format(mapFile, sampleMapFile))
		try:
			with codecs.open(path, "rb", encoding="utf-8") as fileObj:
				db = json.load(fileObj)
		except IOError as e:
			self.rooms = {}
			return self.output("{0}: '{1}'".format(e.strerror, e.filename))
		except ValueError as e:
			self.rooms = {}
			return self.output("Corrupted map database file.")
		self.output("Creating room objects.")
		for vnum, roomDict in iterItems(db):
			newRoom = Room(vnum)
			newRoom.name = roomDict["name"]
			newRoom.desc = roomDict["desc"]
			newRoom.dynamicDesc = roomDict["dynamicDesc"]
			newRoom.note = roomDict["note"]
			newRoom.terrain = roomDict["terrain"]
			newRoom.light = roomDict["light"]
			newRoom.align = roomDict["align"]
			newRoom.portable = roomDict["portable"]
			newRoom.ridable = roomDict["ridable"]
			try:
				newRoom.avoid = roomDict["avoid"]
			except KeyError:
				pass
			newRoom.mobFlags = set(roomDict["mobFlags"])
			newRoom.loadFlags = set(roomDict["loadFlags"])
			newRoom.x = roomDict["x"]
			newRoom.y = roomDict["y"]
			newRoom.z = roomDict["z"]
			newRoom.calculateCost()
			for direction, exitDict in iterItems(roomDict["exits"]):
				newExit = Exit()
				newExit.exitFlags = set(exitDict["exitFlags"])
				newExit.doorFlags = set(exitDict["doorFlags"])
				newExit.door = exitDict["door"]
				newExit.to = exitDict["to"]
				newRoom.exits[direction] = newExit
			self.rooms[vnum] = newRoom
			roomDict.clear()
			del roomDict
		self.currentRoom = self.rooms["0"]
		self.prevRoom = self.rooms["0"]
		self.output("Map database loaded.")

	def loadLabels(self):
		def getLabels(fileName):
			dataDirectory = getDirectoryPath("data")
			fileName = os.path.join(dataDirectory, fileName)
			if os.path.exists(fileName):
				if not os.path.isdir(fileName):
					try:
						with codecs.open(fileName, "rb", encoding="utf-8") as fileObj:
							return json.load(fileObj)
					except IOError as e:
						self.output("{0}: '{1}'".format(e.strerror, e.filename))
						return {}
					except ValueError as e:
						self.output("Corrupted labels database file: {0}".format(fileName))
						return {}
				else:
					self.output("Error: '{0}' is a directory, not a file.".format(fileName))
					return {}
			else:
				return {}
		self.labels.update(getLabels(SAMPLE_LABELS_FILE))
		self.labels.update(getLabels(LABELS_FILE))

	def saveRooms(self):
		self.output("Creating dict from room objects.")
		db = {}
		for vnum, roomObj in iterItems(self.rooms):
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
			for direction, exitObj in iterItems(roomObj.exits):
				newExit = {}
				newExit["exitFlags"] = sorted(exitObj.exitFlags)
				newExit["doorFlags"] = sorted(exitObj.doorFlags)
				newExit["door"] = exitObj.door
				newExit["to"] = exitObj.to
				newRoom["exits"][direction] = newExit
			db[vnum] = newRoom
		self.output("Saving the database in JSon format.")
		mapDirectory = getDirectoryPath("maps")
		mapFile = os.path.join(mapDirectory, MAP_FILE)
		with codecs.open(mapFile, "wb", encoding="utf-8") as fileObj:
			fileObj.write(json.dumps(db, sort_keys=True, indent=2, separators=(",", ": ")))
		self.output("Map Database saved.")

	def saveLabels(self):
		dataDirectory = getDirectoryPath("data")
		labelsFile = os.path.join(dataDirectory, LABELS_FILE)
		with codecs.open(labelsFile, "wb", encoding="utf-8") as fileObj:
			json.dump(self.labels, fileObj, sort_keys=True, indent=2, separators=(",", ": "))

	def sortExits(self, exitsDict):
		return sorted(iterItems(exitsDict), key=lambda direction: DIRECTIONS.index(direction[0]) if direction[0] in DIRECTIONS else len(DIRECTIONS))

	def getVnum(self, roomObj=None):
		result = None
		if roomObj is None:
			roomObj = self.currentRoom
		for vnum, obj in iterItems(self.rooms):
			if obj is roomObj:
				result = vnum
				break
		return result

	def coordinatesAddDirection(self, first, second):
		if first in DIRECTIONS:
			first = DIRECTION_COORDINATES[first]
		if second in DIRECTIONS:
			second = DIRECTION_COORDINATES[second]
		return tuple(sum(coord) for coord in zip(first, second))

	def getNewVnum(self):
		return str(max(int(i) for i in self.rooms) + 1)

	def rdelete(self, *args):
		if args and args[0] is not None and args[0].strip().isdigit():
			if args[0].strip() in self.rooms:
				vnum = args[0].strip()
			else:
				return "Error: the vnum '%s' does not exist." % args[0].strip()
		elif self.isSynced:
			vnum = self.currentRoom.vnum
			self.isSynced = False
			self.currentRoom = self.rooms["0"]
		else:
			return "Syntax: rdelete [vnum]"
		output = "Deleting room '%s' with name '%s'." % (vnum, self.rooms[vnum].name)
		for roomVnum, roomObj in iterItems(self.rooms):
			for direction, exitObj in iterItems(roomObj.exits):
				if exitObj.to == vnum:
					self.rooms[roomVnum].exits[direction].to = "undefined"
		del self.rooms[vnum]
		return output

	def searchRooms(self, *args, **kwArgs):
		exactMatch = bool(kwArgs.get("exactMatch"))
		validArgs = ("name", "desc", "dynamicDesc", "note", "terrain", "light", "align", "portable", "ridable", "x", "y", "z", "mobFlags", "loadFlags", "exitFlags", "doorFlags", "to", "door")
		kwArgs = dict((key, value.strip().lower()) for key, value in iterItems(kwArgs) if key.strip() in validArgs and value.strip())
		results = []
		if not kwArgs:
			return results
		for vnum, roomObj in iterItems(self.rooms):
			keysMatched = 0
			for key, value in iterItems(kwArgs):
				if key in ("name", "desc", "dynamicDesc", "note"):
					roomData = getattr(roomObj, key, "").strip().lower()
					if exactMatch and roomData == value or value in roomData:
						keysMatched += 1
				elif key in ("terrain", "light", "align", "portable", "ridable", "x", "y", "z") and getattr(roomObj, key, "").strip().lower() == value:
					keysMatched += 1
				elif key in ("mobFlags", "loadFlags") and getattr(roomObj, key, set()).intersection(value):
					keysMatched += 1
			for direction, exitObj in iterItems(roomObj.exits):
				for key, value in iterItems(kwArgs):
					if key in ("exitFlags", "doorFlags") and getattr(exitObj, key, set()).intersection(value):
						keysMatched += 1
					elif key in ("to", "door") and getattr(exitObj, key, "").strip().lower() == value:
						keysMatched += 1
			if len(kwArgs) == keysMatched:
				results.append((vnum, roomObj))
		return results

	def rnote(self, *args):
		if not args or args[0] is None or not args[0].strip():
			return "Room note set to '%s'. Use 'rnote [text]' to change it." % self.currentRoom.note
		self.currentRoom.note = args[0].strip()
		return "Room note now set to '%s'." % self.currentRoom.note

	def ralign(self, *args):
		validValues = ("good", "neutral", "evil", "undefined")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return "Room alignment set to '%s'. Use 'ralign [%s]' to change it." % (self.currentRoom.align, " | ".join(validValues))
		self.currentRoom.align = args[0].strip().lower()
		return "Setting room align to '%s'." % self.currentRoom.align

	def rlight(self, *args):
		if not args or not args[0] or args[0].strip() not in LIGHT_SYMBOLS and args[0].strip().lower() not in LIGHT_SYMBOLS.values():
			return "Room light set to '%s'. Use 'rlight [%s]' to change it." % (self.currentRoom.light, " | ".join(set(LIGHT_SYMBOLS.values())))
		try:
			self.currentRoom.light = LIGHT_SYMBOLS[args[0].strip()]
		except KeyError:
			self.currentRoom.light = args[0].strip().lower()
		return "Setting room light to '%s'." % self.currentRoom.light

	def rportable(self, *args):
		validValues = ("portable", "notportable", "undefined")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return "Room portable set to '%s'. Use 'rportable [%s]' to change it." % (self.currentRoom.portable, " | ".join(validValues))
		self.currentRoom.portable = args[0].strip().lower()
		return "Setting room portable to '%s'." % self.currentRoom.portable

	def rridable(self, *args):
		validValues = ("ridable", "notridable", "undefined")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return "Room ridable set to '%s'. Use 'rridable [%s]' to change it." % (self.currentRoom.ridable, " | ".join(validValues))
		self.currentRoom.ridable = args[0].strip().lower()
		self.currentRoom.calculateCost()
		return "Setting room ridable to '%s'." % self.currentRoom.ridable

	def ravoid(self, *args):
		validValues = ("+", "-")
		if not args or not args[0] or args[0].strip().lower() not in validValues:
			return "Room avoid %s. Use 'ravoid [%s]' to change it." % ("enabled" if self.currentRoom.avoid else "disabled", " | ".join(validValues))
		self.currentRoom.avoid = args[0].strip() == "+"
		self.currentRoom.calculateCost()
		return "%s room avoid." % ("Enabling" if self.currentRoom.avoid else "Disabling")

	def rterrain(self, *args):
		if not args or not args[0] or args[0].strip() not in TERRAIN_SYMBOLS and args[0].strip().lower() not in TERRAIN_SYMBOLS.values():
			return "Room terrain set to '%s'. Use 'rterrain [%s | undefined]' to change it." % (self.currentRoom.terrain, " | ".join(TERRAIN_SYMBOLS.values()))
		try:
			self.currentRoom.terrain = TERRAIN_SYMBOLS[args[0].strip()]
		except KeyError:
			self.currentRoom.terrain = args[0].strip().lower()
		self.currentRoom.calculateCost()
		return "Setting room terrain to '%s'." % self.currentRoom.terrain

	def rx(self, *args):
		if args and args[0] and args[0].strip():
			try:
				self.currentRoom.x = int(args[0].strip())
				return "Setting room X coordinate to '%s'." % self.currentRoom.x
			except ValueError:
				return "Error: room coordinates must be comprised of digits only."
		return "Room coordinate X set to '%s'. Use 'rx [digit]' to change it." % self.currentRoom.x

	def ry(self, *args):
		if args and args[0] and args[0].strip():
			try:
				self.currentRoom.y = int(args[0].strip())
				return "Setting room Y coordinate to '%s'." % self.currentRoom.y
			except ValueError:
				return "Error: room coordinates must be comprised of digits only."
		return "Room coordinate Y set to '%s'. Use 'ry [digit]' to change it." % self.currentRoom.y

	def rz(self, *args):
		if args and args[0] and args[0].strip():
			try:
				self.currentRoom.z = int(args[0].strip())
				return "Setting room Z coordinate to '%s'." % self.currentRoom.z
			except ValueError:
				return "Error: room coordinates must be comprised of digits only."
		return "Room coordinate Z set to '%s'. Use 'rz [digit]' to change it." % self.currentRoom.z

	def rmobflags(self, *args):
		regex = re.compile(r"^(?P<mode>%s|%s)\s+(?P<flag>%s)" % (regexFuzzy("add"), regexFuzzy("remove"), "|".join(VALID_MOB_FLAGS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Mob flags set to '%s'. Use 'rmobflags [add | remove] [%s]' to change them." % (", ".join(self.currentRoom.mobFlags), " | ".join(VALID_MOB_FLAGS))
		if "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.mobFlags:
				self.currentRoom.mobFlags.remove(matchDict["flag"])
				return "Mob flag '%s' removed." % matchDict["flag"]
			else:
				return "Mob flag '%s' not set." % matchDict["flag"]
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.mobFlags:
				return "Mob flag '%s' already set." % matchDict["flag"]
			else:
				self.currentRoom.mobFlags.add(matchDict["flag"])
				return "Mob flag '%s' added." % matchDict["flag"]

	def rloadflags(self, *args):
		regex = re.compile(r"^(?P<mode>%s|%s)\s+(?P<flag>%s)" % (regexFuzzy("add"), regexFuzzy("remove"), "|".join(VALID_LOAD_FLAGS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Load flags set to '%s'. Use 'rloadflags [add | remove] [%s]' to change them." % (", ".join(self.currentRoom.loadFlags), " | ".join(VALID_LOAD_FLAGS))
		if "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.loadFlags:
				self.currentRoom.loadFlags.remove(matchDict["flag"])
				return "Load flag '%s' removed." % matchDict["flag"]
			else:
				return "Load flag '%s' not set." % matchDict["flag"]
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.loadFlags:
				return "Load flag '%s' already set." % matchDict["flag"]
			else:
				self.currentRoom.loadFlags.add(matchDict["flag"])
				return "Load flag '%s' added." % matchDict["flag"]

	def exitflags(self, *args):
		regex = re.compile(r"^((?P<mode>%s|%s)\s+)?((?P<flag>%s)\s+)?(?P<direction>%s)" % (regexFuzzy("add"), regexFuzzy("remove"), "|".join(VALID_EXIT_FLAGS), regexFuzzy(DIRECTIONS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Syntax: 'exitflags [add | remove] [%s] [%s]'." % (" | ".join(VALID_EXIT_FLAGS), " | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if direction not in self.currentRoom.exits:
			return "Exit %s does not exist." % direction
		elif not matchDict["mode"]:
			return "Exit flags '%s' set to '%s'." % (direction, ", ".join(self.currentRoom.exits[direction].exitFlags))
		elif "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].exitFlags:
				self.currentRoom.exits[direction].exitFlags.remove(matchDict["flag"])
				return "Exit flag '%s' in direction '%s' removed." % (matchDict["flag"], direction)
			else:
				return "Exit flag '%s' in direction '%s' not set." % (matchDict["flag"], direction)
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].exitFlags:
				return "Exit flag '%s' in direction '%s' already set." % (matchDict["flag"], direction)
			else:
				self.currentRoom.exits[direction].exitFlags.add(matchDict["flag"])
				return "Exit flag '%s' in direction '%s' added." % (matchDict["flag"], direction)

	def doorflags(self, *args):
		regex = re.compile(r"^((?P<mode>%s|%s)\s+)?((?P<flag>%s)\s+)?(?P<direction>%s)" % (regexFuzzy("add"), regexFuzzy("remove"), "|".join(VALID_DOOR_FLAGS), regexFuzzy(DIRECTIONS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Syntax: 'doorflags [add | remove] [%s] [%s]'." % (" | ".join(VALID_DOOR_FLAGS), " | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if direction not in self.currentRoom.exits:
			return "Exit %s does not exist." % direction
		elif not matchDict["mode"]:
			return "Door flags '%s' set to '%s'." % (direction, ", ".join(self.currentRoom.exits[direction].doorFlags))
		elif "remove".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].doorFlags:
				self.currentRoom.exits[direction].doorFlags.remove(matchDict["flag"])
				return "Door flag '%s' in direction '%s' removed." % (matchDict["flag"], direction)
			else:
				return "Door flag '%s' in direction '%s' not set." % (matchDict["flag"], direction)
		elif "add".startswith(matchDict["mode"]):
			if matchDict["flag"] in self.currentRoom.exits[direction].doorFlags:
				return "Door flag '%s' in direction '%s' already set." % (matchDict["flag"], direction)
			else:
				self.currentRoom.exits[direction].doorFlags.add(matchDict["flag"])
				return "Door flag '%s' in direction '%s' added." % (matchDict["flag"], direction)

	def secret(self, *args):
		regex = re.compile(r"^((?P<mode>%s|%s)\s+)?((?P<name>[A-Za-z]+)\s+)?(?P<direction>%s)" % (regexFuzzy("add"), regexFuzzy("remove"), regexFuzzy(DIRECTIONS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Syntax: 'secret [add | remove] [name] [%s]'." % " | ".join(DIRECTIONS)
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if matchDict["mode"] and "add".startswith(matchDict["mode"]):
			if not matchDict["name"]:
				return "Error: 'add' expects a name for the secret."
			elif direction not in self.currentRoom.exits:
				self.currentRoom.exits[direction] = Exit()
			self.currentRoom.exits[direction].exitFlags.add("door")
			self.currentRoom.exits[direction].doorFlags.add("hidden")
			self.currentRoom.exits[direction].door = matchDict["name"]
			return "Adding secret '%s' to direction '%s'." % (matchDict["name"], direction)
		elif direction not in self.currentRoom.exits:
			return "Exit %s does not exist." % direction
		elif not self.currentRoom.exits[direction].door:
			return "No secret %s of here." % direction
		elif not matchDict["mode"]:
			return "Exit '%s' has secret '%s'." % (direction, self.currentRoom.exits[direction].door)
		elif "remove".startswith(matchDict["mode"]):
			if "door" in self.currentRoom.exits[direction].exitFlags:
				self.currentRoom.exits[direction].exitFlags.remove("door")
			if "hidden" in self.currentRoom.exits[direction].doorFlags:
				self.currentRoom.exits[direction].doorFlags.remove("hidden")
			self.currentRoom.exits[direction].door = ""
			return "Secret %s removed." % direction

	def rlink(self, *args):
		regex = re.compile(r"^((?P<mode>%s|%s)\s+)?((?P<oneway>%s)\s+)?((?P<vnum>\d+|undefined)\s+)?(?P<direction>%s)" % (regexFuzzy("add"), regexFuzzy("remove"), regexFuzzy("oneway"), regexFuzzy(DIRECTIONS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return "Syntax: 'rlink [add | remove] [oneway] [vnum] [%s]'." % " | ".join(DIRECTIONS)
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if matchDict["mode"] and "add".startswith(matchDict["mode"]):
			reversedDirection = REVERSE_DIRECTIONS[direction]
			if not matchDict["vnum"]:
				return "Error: 'add' expects a vnum or 'undefined'."
			elif matchDict["vnum"] != "undefined" and matchDict["vnum"] not in self.rooms:
				return "Error: vnum %s not in database." % matchDict["vnum"]
			elif direction not in self.currentRoom.exits:
				self.currentRoom.exits[direction] = Exit()
			self.currentRoom.exits[direction].to = matchDict["vnum"]
			if matchDict["vnum"] == "undefined":
				return "Direction %s now undefined." % direction
			elif not matchDict["oneway"]:
				if reversedDirection not in self.rooms[matchDict["vnum"]].exits or self.rooms[matchDict["vnum"]].exits[reversedDirection].to == "undefined":
					self.rooms[matchDict["vnum"]].exits[reversedDirection] = Exit()
					self.rooms[matchDict["vnum"]].exits[reversedDirection].to = self.currentRoom.vnum
					return "Linking direction %s to %s with name '%s'.\nLinked exit %s in second room with this room." % (direction, matchDict["vnum"], self.rooms[matchDict["vnum"]].name if matchDict["vnum"] in self.rooms else "", reversedDirection)
				else:
					return "Linking direction %s to %s with name '%s'.\nUnable to link exit %s in second room with this room: exit already defined." % (direction, matchDict["vnum"], self.rooms[matchDict["vnum"]].name if matchDict["vnum"] in self.rooms else "", reversedDirection)
			else:
				return "Linking direction %s one way to %s with name '%s'." % (direction, matchDict["vnum"], self.rooms[matchDict["vnum"]].name if matchDict["vnum"] in self.rooms else "")
		elif direction not in self.currentRoom.exits:
			return "Exit %s does not exist." % direction
		elif not matchDict["mode"]:
			return "Exit '%s' links to '%s' with name '%s'." % (direction, self.currentRoom.exits[direction].to, self.rooms[self.currentRoom.exits[direction].to].name if self.currentRoom.exits[direction].to in self.rooms else "")
		elif "remove".startswith(matchDict["mode"]):
			del self.currentRoom.exits[direction]
			return "Exit %s removed." % direction

	def rlabel(self, *args):
		if not args or not args[0]:
			match = None
		else:
			match = re.match(r"^(?P<action>add|delete|info)(?:\s+(?P<label>\S+))?(?:\s+(?P<vnum>\d+))?$", args[0].strip())
		if not match:
			self.output("Syntax: 'rlabel [add|info|delete] [label] [vnum]'. Vnum is only used when adding a room. Leave it blank to use the current room's vnum. Use '_label info all' to get a list of all labels.")
			return None
		else:
			matchDict = match.groupdict()
		if not matchDict["label"]:
			self.output("Error: you need to supply a label.")
			return None
		label = matchDict["label"]
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
					return ["{0} - {1}".format(labelString, vnum) for labelString, vnum in sorted(iterItems(self.labels))]
				else:
					self.output("There aren't any labels in the database yet.")
			elif label not in self.labels:
				self.output("There aren't any labels matching '{0}' in the database.".format(label))
			else:
				self.output("Label '{0}' points to room '{1}'.".format(label, self.labels[label]))

	def rinfo(self, *args):
		if not args or not args[0]:
			vnum = self.currentRoom.vnum
		else:
			vnum = args[0].strip()
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
		result = []
		directionsBuffer = []
		while directionsList:
			item = directionsList.pop()
			if item in DIRECTIONS:
				directionsBuffer.append(item)
			else:
				# The item is not a direction, so process the directions buffer, clear the buffer, and add the resulting list plus the item to the result.
				result.extend(compressDirections(directionsBuffer))
				directionsBuffer = []
				result.append(item)
		# Process any remaining items in the directions buffer.
		if directionsBuffer:
			result.extend(compressDirections(directionsBuffer))
		return "; ".join(result)

	def pathFind(self, origin=None, destination=None, flags=[]):
		"""Find the path"""
		if not origin:
			origin = self.currentRoom
		if destination in self.labels:
			destination = self.labels[destination]
		if destination and destination in self.rooms:
			destination = self.rooms[destination]
		if not origin or not destination:
			self.output("Error: Invalid origin or destination.")
			return None
		if origin is destination:
			self.output("You are already there!")
			return []
		if flags:
			avoidTerrains = frozenset(terrain for terrain in TERRAIN_COSTS if "no{0}".format(terrain) in flags)
		else:
			avoidTerrains = frozenset()
		ignoreVnums = frozenset(("undefined", "death"))
		isDestinationFunc = lambda currentRoomObj: currentRoomObj is destination
		exitIgnoreFunc = lambda exitObj: exitObj.to in ignoreVnums
		exitCostFunc = lambda exitObj, neighborRoomObj: (5 if "door" in exitObj.exitFlags or "climb" in exitObj.exitFlags else 0) + (1000 if "avoid" in exitObj.exitFlags else 0) + (10 if neighborRoomObj.terrain in avoidTerrains else 0)
		exitDestinationFunc = None # lambda exitObj, neighborRoomObj
		return self._pathFind(origin, isDestinationFunc, exitIgnoreFunc, exitCostFunc, exitDestinationFunc)

	def _pathFind(self, origin, isDestinationFunc=None, exitIgnoreFunc=None, exitCostFunc=None, exitDestinationFunc=None):
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
			for exitDirection, exitObj in iterItems(currentRoomObj.exits):
				if exitIgnoreFunc and exitIgnoreFunc(exitObj):
					continue
				# Get a reference to the room object that the exit leads to using the room's vnum.
				neighborRoomObj = self.rooms[exitObj.to]
				# The neighbor room cost should be the sum of all movement costs to get to the neighbor room from the origin room.
				neighborRoomCost = currentRoomCost + neighborRoomObj.cost + exitCostFunc(exitObj, neighborRoomObj) if exitCostFunc else 0
				# We're only interested in the neighbor room if it hasn't been encountered yet, or if the cost of moving from the current room to the neighbor room is less than the cost of moving to the neighbor room from a previously discovered room.
				if neighborRoomObj not in closed or closed[neighborRoomObj] > neighborRoomCost:
					# Add the room object and room cost to the dict of closed rooms, and put it on the opened rooms heap to be processed.
					closed[neighborRoomObj] = neighborRoomCost
					heapq.heappush(opened, (neighborRoomCost, neighborRoomObj))
					# Since the current room is so far the most optimal way into the neighbor room, set it as the parent of the neighbor room.
					parents[neighborRoomObj] = (currentRoomObj, exitDirection)
					if exitDestinationFunc and exitDestinationFunc(exitObj, neighborRoomObj):
						break
		else:
			# The while loop terminated normally (I.E. without encountering a break statement), and the destination was *not* found.
			self.output("No routes found.")
			return None
		# The while statement was broken prematurely, meaning that the destination was found.
		# Find the path from the origin to the destination by traversing the hierarchy of room parents, starting with the current room.
		results = []
		while currentRoomObj is not origin:
			currentRoomObj, direction = parents[currentRoomObj]
			if currentRoomObj.vnum in LEAD_BEFORE_ENTERING_VNUMS and currentRoomObj.exits[direction].to not in LEAD_BEFORE_ENTERING_VNUMS and currentRoomObj is not origin:
				results.append("ride")
			results.append(direction)
			if currentRoomObj.exits[direction].to in LEAD_BEFORE_ENTERING_VNUMS and (currentRoomObj.vnum not in LEAD_BEFORE_ENTERING_VNUMS or currentRoomObj is origin):
				results.append("lead")
			if "door" in currentRoomObj.exits[direction].exitFlags:
				if currentRoomObj.exits[direction].door:
					results.append("open %s %s" % (currentRoomObj.exits[direction].door, direction))
				else:
					results.append("open %s %s" % ("exit", direction))
		return results
