#!/usr/bin/env python

try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import socket
import threading

from .mapperconstants import DIRECTIONS, RUN_DESTINATION_REGEX, USER_COMMANDS_REGEX, TELNET_NEGOTIATION_REGEX, IGNORE_TAGS_REGEX, TINTIN_IGNORE_TAGS_REGEX, TINTIN_SEPARATE_TAGS_REGEX, ROOM_TAGS_REGEX, EXIT_TAGS_REGEX, ANSI_COLOR_REGEX, MOVEMENT_FORCED_REGEX, MOVEMENT_PREVENTED_REGEX, TERRAIN_SYMBOLS
from .mapperworld import iterItems, Room, Exit, World
from .mpi import MPI


class Mapper(threading.Thread, World):
	def __init__(self, client, server, mapperQueue):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self.mapperQueue = mapperQueue
		self.isSynced = False
		self.pathFindResult = []
		self.lastPathFindQuery = ""
		World.__init__(self)

	def output(self, text):
		return self.clientSend(text)

	def clientSend(self, msg):
		self._client.sendall(b"\r\n" + msg.encode("utf-8") + b"\r\n")
		return None

	def serverSend(self, msg):
		self._server.sendall(msg.encode("utf-8") + b"\r\n")
		return None

	def user_command_rinfo(self, *args):
		self.clientSend("\n".join(self.rinfo(*args)))

	def user_command_rlabel(self, *args):
		result = self.rlabel(*args)
		if result:
			self.clientSend("\r\n".join(result))

	def user_command_savemap(self, *args):
		self.saveRooms()

	def user_command_run(self, *args):
		if not args or not args[0]:
			return self.clientSend("Usage: run [label|vnum]")
		self.pathFindResult = []
		argString = args[0].strip()
		if argString == "c":
			if self.lastPathFindQuery:
				match = RUN_DESTINATION_REGEX.match(self.lastPathFindQuery)
				destination = match.group("destination")
				self.clientSend("Continuing walking to destination {0}.".format(destination))
			else:
				return self.clientSend("Error: no previous path to continue.")
		else:
			match = RUN_DESTINATION_REGEX.match(argString)
			destination = match.group("destination")
		flags = match.group("flags")
		if flags:
			flags = flags.split("|")
		else:
			flags = None
		result = self.pathFind(destination=destination, flags=flags)
		if result is not None:
			self.pathFindResult = result
			if result:
				if argString != "c":
					self.lastPathFindQuery = argString
				self.walkNextDirection()

	def user_command_stop(self, *args):
		self.stopRun(verbose=True)

	def user_command_sync(self, *args):
		if not args or not args[0]:
			self.clientSend("Map no longer synced. Auto sync on.")
			self.isSynced = False
			self.serverSend("look")
		else:
			self.sync(vnum=args[0].strip())

	def walkNextDirection(self):
		if self.pathFindResult:
			command = self.pathFindResult.pop()
			while command not in DIRECTIONS and self.pathFindResult:
				self.serverSend(command)
				command = self.pathFindResult.pop()
			self.serverSend(command)
			if not self.pathFindResult:
				self.clientSend("Arriving at destination.")

	def sync(self, name=None, desc=None, exits=None, vnum=None):
		if vnum:
			if vnum in self.labels:
				vnum = self.labels[vnum]
			if vnum in self.rooms:
				self.prevRoom = self.rooms[vnum]
				self.currentRoom = self.rooms[vnum]
				self.isSynced = True
				return self.clientSend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
			else:
				self.clientSend("No such vnum or label: {0}.".format(vnum))
		vnums = []
		for vnum, roomObj in iterItems(self.rooms):
			if roomObj.name == name:
				vnums.append(vnum)
		if not vnums:
			self.clientSend("Current room not in the database. Unable to sync.")
		elif len(vnums) == 1:
			self.prevRoom = self.rooms[vnums[0]]
			self.currentRoom = self.rooms[vnums[0]]
			self.isSynced = True
			self.clientSend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
		else:
			self.clientSend("More than one room in the database matches current room. Unable to sync.")

	def stopRun(self, verbose=False):
		if verbose or self.pathFindResult:
			self.pathFindResult = []
			self.clientSend("Path find canceled.")

	def move(self, dir):
		rooms = self.rooms
		currentRoom = self.currentRoom
		if not dir:
			self.isSynced = False
			return self.clientSend("Map no longer synced!")
		elif dir not in DIRECTIONS:
			self.isSynced = False
			return self.clientSend("Error: Invalid direction '{0}'. Map no longer synced!".format(dir))
		elif dir not in currentRoom.exits:
			self.isSynced = False
			return self.clientSend("Error: direction '{0}' not in database. Map no longer synced!".format(dir))
		vnum = currentRoom.exits[dir].to
		if vnum not in rooms:
			self.isSynced = False
			return self.clientSend("Error: vnum ({0}) in direction ({1}) is not in the database. Map no longer synced!".format(vnum, dir))
		self.prevRoom = rooms[currentRoom.vnum]
		self.currentRoom = rooms[vnum]

	def decode(self, bytes):
		try:
			return bytes.decode("utf-8")
		except UnicodeDecodeError:
			return bytes.decode("latin-1")
		except AttributeError:
			return None

	def run(self):
		while True:
			isFromClient, bytes = self.mapperQueue.get()
			if bytes is None:
				break
			if isFromClient:
				matchedUserInput = USER_COMMANDS_REGEX.match(bytes)
				if matchedUserInput:
					getattr(self, "user_command_{0}".format(self.decode(matchedUserInput.group("command"))))(self.decode(matchedUserInput.group("arguments")))
			else:
				received = self.decode(TELNET_NEGOTIATION_REGEX.sub("", bytes))
				received = IGNORE_TAGS_REGEX.sub("", received)
				received = ANSI_COLOR_REGEX.sub("", received)
				received = received.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"').replace("\r\n", "\n")
				movementForcedSearch = MOVEMENT_FORCED_REGEX.search(received)
				if movementForcedSearch or MOVEMENT_PREVENTED_REGEX.search(received):
					self.stopRun(verbose=False)
				if movementForcedSearch and self.isSynced:
					if movementForcedSearch.group("ignore"):
						self.currentRoom = self.rooms[self.prevRoom.vnum]
						self.clientSend("Forced movement ignored, still synced.")
						continue
					else:
						self.isSynced = False
						self.clientSend("Forced movement, no longer synced.")
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
		self.clientSend("Exiting mapper thread.")


class Proxy(threading.Thread):
	def __init__(self, client, server, mapperQueue):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self._mapperQueue = mapperQueue

	def run(self):
		while True:
			bytes = self._client.recv(4096)
			if not bytes:
				break
			elif USER_COMMANDS_REGEX.match(bytes):
				# True tells the mapper thread that the bytes are from the user's Mud client.
				self._mapperQueue.put((True, bytes))
				continue
			self._server.sendall(bytes)


class Server(threading.Thread):
	def __init__(self, client, server, mapperQueue, mpiQueue, isTinTin=None):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self._mapperQueue = mapperQueue
		self._mpiQueue = mpiQueue
		self.isTinTin = bool(isTinTin)

	def upperMatch(self, match):
		return b"".join((match.group("tag").upper(), b":", match.group("text").replace(b"\r\n", b" ").strip() if match.group("text") else b"", b":", match.group("tag").upper(), b"\r\n" if match.group("tag") != b"prompt" else b""))

	def run(self):
		while True:
			bytes = self._server.recv(4096)
			if not bytes:
				break
			# False tells the mapper thread that the bytes are *not* from the user's Mud client.
			self._mapperQueue.put((False, bytes))
			self._mpiQueue.put(bytes)
			if self.isTinTin:
				bytes = TINTIN_IGNORE_TAGS_REGEX.sub(b"", bytes)
				bytes = TINTIN_SEPARATE_TAGS_REGEX.sub(self.upperMatch, bytes)
				bytes = bytes.replace(b"&amp;", b"&").replace(b"&lt;", b"<").replace(b"&gt;", b">").replace(b"&#39;", b"'").replace(b"&quot;", b'"')
			self._client.sendall(bytes)


def main(isTinTin=None):
	proxySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.bind(("", 4000))
	proxySocket.listen(1)
	clientConnection, proxyAddress = proxySocket.accept()
	serverConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serverConnection.connect(("193.134.218.99", 4242))
	mapperQueue = Queue()
	mpiQueue = Queue()
	mapperThread = Mapper(client=clientConnection, server=serverConnection, mapperQueue=mapperQueue)
	mpiThread = MPI(client=clientConnection, server=serverConnection, mpiQueue=mpiQueue, isTinTin=isTinTin)
	proxyThread = Proxy(client=clientConnection, server=serverConnection, mapperQueue=mapperQueue)
	serverThread = Server(client=clientConnection, server=serverConnection, mapperQueue=mapperQueue, mpiQueue=mpiQueue, isTinTin=isTinTin)
	serverThread.start()
	proxyThread.start()
	mapperThread.start()
	mpiThread.start()
	serverThread.join()
	try:
		serverConnection.shutdown(socket.SHUT_RDWR)
	except:
		pass
	mapperQueue.put((None, None))
	mpiQueue.put(None)
	mapperThread.join()
	mpiThread.join()
	try:
		clientConnection.sendall(b"\r\n")
		clientConnection.shutdown(socket.SHUT_RDWR)
	except:
		pass
	proxyThread.join()
	serverConnection.close()
	clientConnection.close()
