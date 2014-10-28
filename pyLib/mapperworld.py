#!/usr/bin/env python

import codecs
import heapq
import json
import os.path
import re

try:
	import ujson
except ImportError:
	ujson = json

from .mapperconstants import IS_PYTHON_2, DIRECTIONS, MAP_FILE, SAMPLE_MAP_FILE, LABELS_FILE, SAMPLE_LABELS_FILE, AVOID_DYNAMIC_DESC_REGEX, AVOID_VNUMS, LEAD_BEFORE_ENTERING_VNUMS, TERRAIN_COSTS

def iterItems(dictionary, **kw):
	if IS_PYTHON_2:
		return iter(dictionary.iteritems(**kw))
	else:
		return iter(dictionary.items(**kw))


class Room(object):
	def __init__(self):
		self.name = ""
		self.desc = ""
		self.dynamicDesc = ""
		self.vnum = ""
		self.note = ""
		self.terrain = "undefined"
		self.light = "undefined"
		self.align = "undefined"
		self.portable = "undefined"
		self.ridable = "undefined"
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


class Exit(object):
	def __init__(self):
		self.to = ""
		self.exitFlags = set()
		self.door = ""
		self.doorFlags = set()


class World(object):
	def __init__(self):
		self.rooms = {}
		self.labels = {}
		self.currentRoom = Room()
		self.prevRoom = self.currentRoom
		self.loadRooms()
		self.loadLabels()

	def output(self, text):
		print(text)
		return None

	def loadRooms(self):
		self.output("Loading the JSon database file.")
		if os.path.exists(MAP_FILE):
			if not os.path.isdir(MAP_FILE):
				path = MAP_FILE
			else:
				path = None
				self.output("Error: '{0}' is a directory, not a file.".format(MAP_FILE))
		elif os.path.exists(SAMPLE_MAP_FILE):
			if not os.path.isdir(SAMPLE_MAP_FILE):
				path = SAMPLE_MAP_FILE
			else:
				path = None
				self.output("Error: '{0}' is a directory, not a file.".format(SAMPLE_MAP_FILE))
		if not path:
			return self.output("Error: neither '{0}' nor '{1}' can be found.".format(MAP_FILE, SAMPLE_MAP_FILE))
		try:
			with codecs.open(path, "rb", encoding="utf-8") as fileObj:
				db = ujson.load(fileObj)
		except IOError as e:
			self.rooms = {}
			return self.output("{0}: '{1}'".format(e.strerror, e.filename))
		except ValueError as e:
			self.rooms = {}
			return self.output("Corrupted map database file.")
		self.output("Creating room objects.")
		for vnum, roomDict in iterItems(db):
			newRoom = Room()
			newRoom.name = roomDict["name"]
			newRoom.desc = roomDict["desc"]
			newRoom.dynamicDesc = roomDict["dynamicDesc"]
			newRoom.vnum = vnum
			newRoom.note = roomDict["note"]
			newRoom.terrain = roomDict["terrain"]
			newRoom.light = roomDict["light"]
			newRoom.align = roomDict["align"]
			newRoom.portable = roomDict["portable"]
			newRoom.ridable = roomDict["ridable"]
			newRoom.mobFlags = set(roomDict["mobFlags"])
			newRoom.loadFlags = set(roomDict["loadFlags"])
			newRoom.x = roomDict["x"]
			newRoom.y = roomDict["y"]
			newRoom.z = roomDict["z"]
			try:
				newRoom.cost = TERRAIN_COSTS[newRoom.terrain]
			except KeyError:
				newRoom.cost = TERRAIN_COSTS["undefined"]
			if vnum in AVOID_VNUMS or AVOID_DYNAMIC_DESC_REGEX.search(newRoom.dynamicDesc):
				newRoom.cost += 1000.0
			if newRoom.ridable == "notridable":
				newRoom.cost += 5.0
			for direction, exitDict in iterItems(roomDict["exits"]):
				newExit = Exit()
				newExit.exitFlags = set(exitDict["exitFlags"])
				newExit.doorFlags = set(exitDict["doorFlags"])
				newExit.door = exitDict["door"]
				newExit.to = exitDict["to"]
				newRoom.exits[direction] = newExit
			self.rooms[vnum] = newRoom
		self.currentRoom = self.rooms["0"]
		self.prevRoom = self.rooms["0"]
		self.output("Map database loaded.")

	def loadLabels(self):
		def getLabels(fileName):
			if os.path.exists(fileName):
				if not os.path.isdir(fileName):
					try:
						with codecs.open(fileName, "rb", encoding="utf-8") as fileObj:
							return ujson.load(fileObj)
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
			newRoom["mobFlags"] = list(roomObj.mobFlags)
			newRoom["loadFlags"] = list(roomObj.loadFlags)
			newRoom["x"] = roomObj.x
			newRoom["y"] = roomObj.y
			newRoom["z"] = roomObj.z
			newRoom["exits"] = {}
			for direction, exitObj in iterItems(roomObj.exits):
				newExit = {}
				newExit["exitFlags"] = list(exitObj.exitFlags)
				newExit["doorFlags"] = list(exitObj.doorFlags)
				newExit["door"] = exitObj.door
				newExit["to"] = exitObj.to
				newRoom["exits"][direction] = newExit
			db[vnum] = newRoom
		self.output("Saving the database in JSon format.")
		with codecs.open(MAP_FILE, "wb", encoding="utf-8") as fileObj:
			ujson.dump(db, fileObj)
		self.output("Map Database saved.")

	def saveLabels(self):
		with codecs.open(LABELS_FILE, "wb", encoding="utf-8") as fileObj:
			json.dump(self.labels, fileObj, sort_keys=True, indent=2, separators=(",", ": "))

	def sortExits(self, exitsDict):
		return sorted(iterItems(exitsDict), key=lambda direction:DIRECTIONS.index(direction[0]) if direction[0] in DIRECTIONS else len(DIRECTIONS))

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
		if origin == destination:
			self.output("You are already there!")
			return []
		if flags:
			avoidTerrains = [terrain for terrain in TERRAIN_COSTS if "no{0}".format(terrain) in flags]
		else:
			avoidTerrains = []
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
			if currentRoomObj == destination:
				# We successfully found a path from the origin to the destination.
				# find the path from the origin to the destination by traversing the rooms that we passed through to get here.
				result = []
				while currentRoomObj != origin:
					currentRoomObj, direction = parents[currentRoomObj]
					if currentRoomObj.vnum in LEAD_BEFORE_ENTERING_VNUMS and currentRoomObj.exits[direction].to not in LEAD_BEFORE_ENTERING_VNUMS and currentRoomObj != origin:
						result.append("ride")
					result.append(direction)
					if currentRoomObj.exits[direction].to in LEAD_BEFORE_ENTERING_VNUMS and (currentRoomObj.vnum not in LEAD_BEFORE_ENTERING_VNUMS or currentRoomObj == origin):
						result.append("lead")
					if "door" in currentRoomObj.exits[direction].exitFlags:
						if currentRoomObj.exits[direction].door:
							result.append("open {0} {1}".format(currentRoomObj.exits[direction].door, direction))
						else:
							result.append("open {0} {1}".format("exit", direction))
				return result
			# If we're here, the current room isn't the destination.
			# Loop through the exits, and process each room linked to the current room.
			for exitDirection, exitObj in iterItems(currentRoomObj.exits):
				# Ignore exits that link to undefined or death trap rooms.
				if exitObj.to=="undefined" or exitObj.to=="death":
					continue
				# Get a reference to the room object that the exit leads to using the room's vnum.
				neighborRoomObj = self.rooms[exitObj.to]
				# The neighbor room cost should be the sum of all movement costs to get to the neighbor room from the origin room.
				neighborRoomCost = currentRoomCost + neighborRoomObj.cost
				if "door" in exitObj.exitFlags or "climb" in exitObj.exitFlags:
					neighborRoomCost += 5.0
				if flags:
					if neighborRoomObj.terrain in avoidTerrains:
						neighborRoomCost += 10.0
				# We're only interested in the neighbor room if it hasn't been encountered yet, or if the cost of moving from the current room to the neighbor room is less than the cost of moving to the neighbor room from a previously discovered room.
				if neighborRoomObj not in closed or closed[neighborRoomObj] > neighborRoomCost:
					# Add the room object and room cost to the dict of closed rooms, and put it on the opened rooms heap to be processed.
					closed[neighborRoomObj] = neighborRoomCost
					heapq.heappush(opened, (neighborRoomCost, neighborRoomObj))
					# Since the current room is so far the most optimal way into the neighbor room, set it as the parent of the neighbor room.
					parents[neighborRoomObj] = (currentRoomObj, exitDirection)
		self.output("No routes found.")
		return None
