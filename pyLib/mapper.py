#!/usr/bin/env python

import codecs
import heapq
import os.path
try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import re
import socket
import threading

try:
	import ujson as json
except ImportError:
	import json

from mapperconstants import IS_PYTHON_2, IS_PYTHON_3, IS_TINTIN, MAP_FILE, SAMPLE_MAP_FILE, LABELS_FILE, SAMPLE_LABELS_FILE, DIRECTIONS, USER_COMMANDS_REGEX, IGNORE_TAGS_REGEX, TINTIN_IGNORE_TAGS_REGEX, TINTIN_SEPARATE_TAGS_REGEX, ROOM_TAGS_REGEX, EXIT_TAGS_REGEX, ANSI_COLOR_REGEX, AVOID_DYNAMIC_DESC_REGEX, MOVEMENT_FORCED_REGEX, MOVEMENT_PREVENTED_REGEX, AVOID_VNUMS, TERRAIN_COSTS, TERRAIN_SYMBOLS

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


class Mapper(threading.Thread):
	def __init__(self, proxy, server, mapperQueue):
		threading.Thread.__init__(self)
		self._proxy = proxy
		self._server = server
		self.mapperQueue = mapperQueue
		self.rooms = {}
		self.labels = {}
		self.isSynced = False
		self.pathFindResult = []
		self.lastPathFindQuery = ""
		self.loadDatabase()
		self.loadLabels()

	def loadDatabase(self):
		self.proxySend("Loading the JSon database file.")
		if os.path.exists(MAP_FILE):
			if not os.path.isdir(MAP_FILE):
				path = MAP_FILE
			else:
				path = None
				self.proxySend("Error: '{0}' is a directory, not a file.".format(MAP_FILE))
		elif os.path.exists(SAMPLE_MAP_FILE):
			if not os.path.isdir(SAMPLE_MAP_FILE):
				path = SAMPLE_MAP_FILE
			else:
				path = None
				self.proxySend("Error: '{0}' is a directory, not a file.".format(SAMPLE_MAP_FILE))
		if not path:
			return self.proxySend("Error: neither '{0}' nor '{1}' can be found.".format(MAP_FILE, SAMPLE_MAP_FILE))
		try:
			with codecs.open(path, "rb", encoding="utf-8") as fileObj:
				db = json.load(fileObj)
		except IOError as e:
			self.rooms = {}
			return self.proxySend("{0}: '{1}'".format(e.strerror, e.filename))
		except ValueError as e:
			self.rooms = {}
			return self.proxySend("Corrupted map database file.")
		self.proxySend("Creating room objects.")
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
		self.prevRoom = self.rooms["0"]
		self.currentRoom = self.rooms["0"]
		self.proxySend("Map database loaded.")

	def loadLabels(self):
		def getLabels(fileName):
			if os.path.exists(fileName):
				if not os.path.isdir(fileName):
					try:
						with codecs.open(fileName, "rb", encoding="utf-8") as fileObj:
							return json.load(fileObj)
					except IOError as e:
						self.proxySend("{0}: '{1}'".format(e.strerror, e.filename))
						return {}
					except ValueError as e:
						self.proxySend("Corrupted labels database file: {0}".format(fileName))
						return {}
				else:
					self.proxySend("Error: '{0}' is a directory, not a file.".format(fileName))
					return {}
			else:
				return {}
		self.labels.update(getLabels(SAMPLE_LABELS_FILE))
		self.labels.update(getLabels(LABELS_FILE))

	def saveDatabase(self):
		self.proxySend("Creating dict from room objects.")
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
		self.proxySend("Saving the database in JSon format.")
		with codecs.open(MAP_FILE, "wb", encoding="utf-8") as fileObj:
			json.dump(db, fileObj)
		self.proxySend("Map Database saved.")

	def saveLabels(self):
		with codecs.open(LABELS_FILE, "wb", encoding="utf-8") as fileObj:
			json.dump(self.labels, fileObj)

	def proxySend(self, msg):
		self._proxy.sendall(b"\r\n" + msg.encode("utf-8") + b"\r\n")

	def serverSend(self, msg):
		self._server.sendall(msg.encode("utf-8") + b"\r\n")

	def user_command_rlabel(self, *args):
		if not args or not args[0]:
			match = None
		else:
			match = re.match(r"^(?P<action>add|delete|info)(?:\s+(?P<label>\S+))?(?:\s+(?P<vnum>\d+))?$", args[0].strip())
		if not match:
			return self.proxySend("Syntax: 'rlabel [add|info|delete] [label] [vnum]'. Vnum is only used when adding a room. Leave it blank to use the current room's vnum. Use '_label info all' to get a list of all labels.")
		else:
			matchDict = match.groupdict()
		if not matchDict["label"]:
			return self.proxySend("Error: you need to supply a label.")
		label = matchDict["label"]
		if matchDict["action"] == "add":
			if not matchDict["vnum"]:
				vnum = self.currentRoom.vnum
				self.proxySend("adding the label '{0}' to current room with VNum '{1}'.".format(label, vnum))
			else:
				vnum = matchDict["vnum"]
				self.proxySend("adding the label '{0}' with VNum '{1}'.".format(label, vnum))
			self.labels[label] = vnum
			self.saveLabels()
		elif matchDict["action"] == "delete":
			if label not in self.labels:
				return self.proxySend("There aren't any labels matching '{0}' in the database.".format(label))
			self.proxySend("Deleting label '{0}'.".format(label))
			del self.labels[label]
			self.saveLabels()
		elif matchDict["action"] == "info":
			if "all".startswith(label):
				if self.labels:
					for key, value in sorted(iterItems(self.labels)):
						self.proxySend("{0} - {1}".format(key, value))
				else:
					self.proxySend("There aren't any labels in the database yet.")
			elif label not in self.labels:
				self.proxySend("There aren't any labels matching '{0}' in the database.".format(label))
			else:
				self.proxySend("Label '{0}' points to room '{1}'.".format(label, self.labels[label]))

	def user_command_run(self, *args):
		"""Find the path"""
		if not args or not args[0]:
			return self.proxySend("Usage: run [label|vnum]")
		else:
			destination = args[0].strip()
		self.pathFindResult = []
		origin = self.currentRoom
		if destination == "c":
			if self.lastPathFindQuery:
				destination = self.lastPathFindQuery
				self.proxySend("Continuing walking to vnum {0}.".format(self.lastPathFindQuery))
			else:
				return self.proxySend("Error: no previous path to continue.")
		elif destination in self.labels:
			destination = self.labels[destination]
		if destination and destination in self.rooms:
			self.lastPathFindQuery = destination
			destination = self.rooms[destination]
		if not origin or not destination:
			return self.proxySend("Error: Invalid origin or destination.")
		elif origin == destination:
			return self.proxySend("You are already there!")
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
				while currentRoomObj != origin:
					currentRoomObj, direction = parents[currentRoomObj]
					self.pathFindResult.append(direction)
					if "door" in currentRoomObj.exits[direction].exitFlags:
						if currentRoomObj.exits[direction].door:
							self.pathFindResult.append("open {0} {1}".format(currentRoomObj.exits[direction].door, direction))
						else:
							self.pathFindResult.append("open {0} {1}".format("exit", direction))
				break
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
				# We're only interested in the neighbor room if it hasn't been encountered yet, or if the cost of moving from the current room to the neighbor room is less than the cost of moving to the neighbor room from a previously discovered room.
				if neighborRoomObj not in closed or closed[neighborRoomObj] > neighborRoomCost:
					# Add the room object and room cost to the dict of closed rooms, and put it on the opened rooms heap to be processed.
					closed[neighborRoomObj] = neighborRoomCost
					heapq.heappush(opened, (neighborRoomCost, neighborRoomObj))
					# Since the current room is so far the most optimal way into the neighbor room, set it as the parent of the neighbor room.
					parents[neighborRoomObj] = (currentRoomObj, exitDirection)
		if not self.pathFindResult:
			self.proxySend("No routes found.")
		else:
			self.walkNextDirection()

	def user_command_savemap(self, *args):
		self.saveDatabase()

	def walkNextDirection(self):
		if self.pathFindResult:
			command = self.pathFindResult.pop()
			while command not in DIRECTIONS:
				self.serverSend(command)
				command = self.pathFindResult.pop()
			self.serverSend(command)
			if not self.pathFindResult:
				self.proxySend("Arriving at destination.")

	def user_command_rinfo(self, *args):
		if not args or not args[0]:
			vnum = self.currentRoom.vnum
		else:
			vnum = args[0].strip()
		if vnum in self.labels:
			vnum = self.labels[vnum]
		if vnum in self.rooms:
			room = self.rooms[vnum]
		else:
			return self.proxySend("Error: No such vnum or label, '%s'" % vnum)
		info = []
		info.append("vnum: '{0}'".format(room.vnum))
		info.append("Name: '{0}'".format(room.name))
		info.append("Description:\n-----\n{0}\n-----".format(room.desc))
		info.append("Dynamic Desc:\n-----\n{0}\n-----".format(room.dynamicDesc))
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
		for direction, exitcls in iterItems(room.exits):
			info.append("-----")
			info.append("Direction: '{0}'".format(direction))
			info.append("To: '{0}'".format(exitcls.to))
			info.append("Exit Flags: '{0}'".format(", ".join(exitcls.exitFlags)))
			info.append("Door Name: '{0}'".format(exitcls.door))
			info.append("Door Flags: '{0}'".format(", ".join(exitcls.doorFlags)))
		self.proxySend("\n".join(info))

	def sync(self, name=None, desc=None, exits=None, vnum=None):
		if vnum:
			if vnum in self.labels:
				vnum = self.labels[vnum]
			if vnum in self.rooms:
				self.prevRoom = self.rooms[vnum]
				self.currentRoom = self.rooms[vnum]
				self.isSynced = True
				return self.proxySend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
			else:
				self.proxySend("No such vnum or label: {0}.".format(vnum))
		vnums = []
		for vnum, roomObj in iterItems(self.rooms):
			if roomObj.name == name:
				vnums.append(vnum)
		if not vnums:
			self.proxySend("Current room not in the database. Unable to sync.")
		elif len(vnums) == 1:
			self.prevRoom = self.rooms[vnums[0]]
			self.currentRoom = self.rooms[vnums[0]]
			self.isSynced = True
			self.proxySend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
		else:
			self.proxySend("More than one room in the database matches current room. Unable to sync.")

	def user_command_sync(self, *args):
		if not args or not args[0]:
			self.proxySend("Map no longer synced. Auto sync on.")
			self.isSynced = False
			self.serverSend("look")
		else:
			self.sync(vnum=args[0].strip())

	def stopRun(self, verbose=False):
		if verbose or self.pathFindResult:
			self.pathFindResult = []
			self.proxySend("Path find canceled.")

	def user_command_stop(self, *args):
		self.stopRun(verbose=True)

	def move(self, dir):
		if not dir:
			self.isSynced = False
			return self.proxySend("Map no longer synced!")
		elif dir not in DIRECTIONS:
			self.isSynced = False
			return self.proxySend("Error: Invalid direction '{0}'. Map no longer synced!".format(dir))
		elif dir not in self.currentRoom.exits:
			self.isSynced = False
			return self.proxySend("Error: direction '{0}' not in database. Map no longer synced!".format(dir))
		vnum = self.currentRoom.exits[dir].to
		if vnum not in self.rooms:
			self.isSynced = False
			return self.proxySend("Error: vnum ({0}) in direction ({1}) is not in the database. Map no longer synced!".format(vnum, dir))
		self.prevRoom = self.rooms[self.currentRoom.vnum]
		self.currentRoom = self.rooms[vnum]

	def decode(self, bytes):
		try:
			return bytes.decode("utf-8")
		except UnicodeDecodeError:
			return bytes.decode("latin-1")
		except AttributeError:
			return None

	def run(self):
		while True:
			fromProxy, bytes = self.mapperQueue.get()
			if bytes is None:
				break
			if fromProxy:
				matchedUserInput = USER_COMMANDS_REGEX.match(bytes)
				if matchedUserInput:
					getattr(self, "user_command_{0}".format(self.decode(matchedUserInput.group("command"))))(self.decode(matchedUserInput.group("arguments")))
			else:
				received = self.decode(bytes)
				received = IGNORE_TAGS_REGEX.sub("", received)
				received = ANSI_COLOR_REGEX.sub("", received)
				received = received.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"').replace("\r\n", "\n")
				movementForcedSearch = MOVEMENT_FORCED_REGEX.search(received)
				if movementForcedSearch or MOVEMENT_PREVENTED_REGEX.search(received):
					self.stopRun(verbose=False)
				if movementForcedSearch and self.isSynced:
					if movementForcedSearch.group("ignore"):
						self.currentRoom = self.rooms[self.prevRoom.vnum]
						self.proxySend("Forced movement ignored, still synced.")
						continue
					else:
						self.isSynced = False
						self.proxySend("Forced movement, no longer synced.")
				roomSearch = ROOM_TAGS_REGEX.search(received)
				if not roomSearch:
					continue
				roomDict = roomSearch.groupdict()
				if roomDict["movement"] and self.isSynced:
					self.move(roomDict["movementDir"])
					if self.pathFindResult:
						self.walkNextDirection()
				if roomDict["name"] in ("You just see a dense fog around you...", "It is pitch black..."):
					continue
				newRoom = Room()
				newRoom.name = roomDict["name"]
				newRoom.desc = roomDict["description"]
				newRoom.dynamicDesc = roomDict["dynamic"]
				newRoom.exits = {}
				if roomDict["exits"]:
					for direction in EXIT_TAGS_REGEX.findall(roomDict["exits"]):
						newRoom.exits[direction] = Exit()
				prompt = roomDict["prompt"]
				if not self.isSynced:
					self.sync(newRoom.name)
		self.proxySend("Exiting mapper thread.")

class Connection(threading.Thread):
	def __init__(self, inbound, outbound, type, mapperQueue):
		threading.Thread.__init__(self)
		self._inbound = inbound
		self._outbound = outbound
		self._mapperQueue = mapperQueue
		self.isProxy = type == "proxy"
		self.isServer = type == "server"

	def upperMatch(self, match):
		return b"".join((match.group("tag").upper(), b":", match.group("text").replace(b"\r\n", b" ").strip() if match.group("text") else b"", b":", match.group("tag").upper(), b"\r\n" if match.group("tag") != b"prompt" else b""))

	def run(self):
		while True:
			bytes = self._inbound.recv(4096)
			if not bytes:
				break
			elif self.isServer:
				self._mapperQueue.put((self.isProxy, bytes))
				if IS_TINTIN:
					bytes = TINTIN_IGNORE_TAGS_REGEX.sub(b"", bytes)
					bytes = TINTIN_SEPARATE_TAGS_REGEX.sub(self.upperMatch, bytes)
					bytes = bytes.replace(b"&amp;", b"&").replace(b"&lt;", b"<").replace(b"&gt;", b">").replace(b"&#39;", b"'").replace(b"&quot;", b'"')
			elif USER_COMMANDS_REGEX.match(bytes):
				self._mapperQueue.put((self.isProxy, bytes))
				continue
			self._outbound.sendall(bytes)


def main():
	proxySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.bind(("", 4000))
	proxySocket.listen(1)
	proxyConnection, proxyAddress = proxySocket.accept()
	serverConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serverConnection.connect(("193.134.218.99", 4242))
	q = Queue()
	mapperThread = Mapper(proxy=proxyConnection, server=serverConnection, mapperQueue=q)
	proxyThread = Connection(inbound=proxyConnection, outbound=serverConnection, type="proxy", mapperQueue=q)
	serverThread = Connection(inbound=serverConnection, outbound=proxyConnection, type="server", mapperQueue=q)
	serverThread.start()
	proxyThread.start()
	mapperThread.start()
	serverThread.join()
	serverConnection.shutdown(socket.SHUT_RDWR)
	q.put((None, None))
	mapperThread.join()
	proxyConnection.sendall(b"\r\n")
	proxyConnection.shutdown(socket.SHUT_RDWR)
	proxyThread.join()
	serverConnection.close()
	proxyConnection.close()

if __name__ == "__main__":
	main()
