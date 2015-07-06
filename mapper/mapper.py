# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import re
import socket
import sys
from telnetlib import IAC, DO, GA, TTYPE, NAWS
import threading
from timeit import default_timer

from .mapperconstants import DIRECTIONS, REVERSE_DIRECTIONS, MPI_REGEX, RUN_DESTINATION_REGEX, USER_COMMANDS_REGEX, MAPPER_IGNORE_TAGS_REGEX, TINTIN_IGNORE_TAGS_REGEX, TINTIN_SEPARATE_TAGS_REGEX, ROOM_TAGS_REGEX, EXIT_TAGS_REGEX, ANSI_COLOR_REGEX, MOVEMENT_FORCED_REGEX, MOVEMENT_PREVENTED_REGEX, TERRAIN_COSTS, TERRAIN_SYMBOLS, LIGHT_SYMBOLS, XML_UNESCAPE_PATTERNS
from .mapperworld import Room, Exit, World
from .mpi import MPI
from .utils import iterItems, decodeBytes, multiReplace, TelnetStripper, regexFuzzy


IAC_GA = IAC + GA

class Mapper(threading.Thread, World):
	def __init__(self, client, server, mapperQueue, isTinTin):
		threading.Thread.__init__(self)
		self.daemon = True
		# Initialize the timer.
		self.initTimer = default_timer()
		self._client = client
		self._server = server
		self.mapperQueue = mapperQueue
		self.isTinTin = bool(isTinTin)
		self.autoMapping = False
		self.autoUpdating = False
		self.autoMerging = True
		self.autoLinking = True
		self.autoWalkDirections = []
		self.lastPathFindQuery = ""
		self.lastPrompt = ">"
		World.__init__(self)

	def output(self, text):
		# Override World.output.
		return self.clientSend(text)

	def clientSend(self, msg):
		self._client.sendall(("%s\r\nPROMPT:%s:PROMPT" % (msg, self.lastPrompt)).encode("utf-8").replace(IAC, IAC+IAC) + IAC_GA)
		return None

	def serverSend(self, msg):
		self._server.sendall(msg.encode("utf-8").replace(IAC, IAC + IAC) + b"\r\n")
		return None

	def user_command_gettimer(self, *args):
		self.clientSend("TIMER:%d:TIMER" % int(default_timer() - self.initTimer))

	def user_command_gettimerms(self, *args):
		self.clientSend("TIMERMS:%d:TIMERMS" % int((default_timer() - self.initTimer) * 1000))

	def user_command_secretaction(self, *args):
		regex = re.compile(r"^\s*(?P<action>.+)\s+(?P<direction>%s)$" % regexFuzzy(DIRECTIONS))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return self.clientSend("Syntax: 'secretaction [action] [%s]'." % " | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		if direction in self.currentRoom.exits and self.currentRoom.exits[direction].door:
			return self.serverSend("%s %s %s" % (matchDict["action"], self.currentRoom.exits[direction].door, direction[0]))
		else:
			return self.serverSend("%s exit %s" % (matchDict["action"], direction[0]))

	def user_command_automap(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoMapping = not self.autoMapping
		else:
			self.autoMapping = args[0].strip().lower() == "on"
		self.clientSend("Auto Mapping %s." % ("on" if self.autoMapping else "off"))

	def user_command_autoupdate(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoUpdating = not self.autoUpdating
		else:
			self.autoUpdating = args[0].strip().lower() == "on"
		self.clientSend("Auto Updating Room Names and Descriptions %s." % ("on" if self.autoUpdating else "off"))

	def user_command_automerge(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoMerging = not self.autoMerging
		else:
			self.autoMerging = args[0].strip().lower() == "on"
		self.clientSend("Auto Merging %s." % ("on" if self.autoMerging else "off"))

	def user_command_autolink(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoLinking = not self.autoLinking
		else:
			self.autoLinking = args[0].strip().lower() == "on"
		self.clientSend("Auto Linking %s." % ("on" if self.autoLinking else "off"))

	def user_command_rdelete(self, *args):
		self.clientSend(self.rdelete(*args))

	def user_command_rnote(self, *args):
		self.clientSend(self.rnote(*args))

	def user_command_ralign(self, *args):
		self.clientSend(self.ralign(*args))

	def user_command_rlight(self, *args):
		self.clientSend(self.rlight(*args))

	def user_command_rportable(self, *args):
		self.clientSend(self.rportable(*args))

	def user_command_rridable(self, *args):
		self.clientSend(self.rridable(*args))

	def user_command_rterrain(self, *args):
		self.clientSend(self.rterrain(*args))

	def user_command_rx(self, *args):
		self.clientSend(self.rx(*args))

	def user_command_ry(self, *args):
		self.clientSend(self.ry(*args))

	def user_command_rz(self, *args):
		self.clientSend(self.rz(*args))

	def user_command_rmobflags(self, *args):
		self.clientSend(self.rmobflags(*args))

	def user_command_rloadflags(self, *args):
		self.clientSend(self.rloadflags(*args))

	def user_command_exitflags(self, *args):
		self.clientSend(self.exitflags(*args))

	def user_command_doorflags(self, *args):
		self.clientSend(self.doorflags(*args))

	def user_command_secret(self, *args):
		self.clientSend(self.secret(*args))

	def user_command_rlink(self, *args):
		self.clientSend(self.rlink(*args))

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
		self.autoWalkDirections = []
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
			self.autoWalkDirections = result
			if result:
				if argString != "c":
					self.lastPathFindQuery = argString
				self.walkNextDirection()

	def user_command_stop(self, *args):
		self.clientSend(self.stopRun())

	def user_command_sync(self, *args):
		if not args or not args[0]:
			self.clientSend("Map no longer synced. Auto sync on.")
			self.isSynced = False
			self.serverSend("look")
		else:
			self.sync(vnum=args[0].strip())

	def walkNextDirection(self):
		if self.autoWalkDirections:
			command = self.autoWalkDirections.pop()
			while command not in DIRECTIONS and self.autoWalkDirections:
				# command is a non-direction such as 'lead' or 'ride'.
				self.serverSend(command)
				command = self.autoWalkDirections.pop()
			# Command is a valid direction.
			if not self.autoWalkDirections:
				# There will be no more auto-walk directions after this one is sent.
				self.clientSend("Arriving at destination.")
			# Send the first character of the direction to Mume.
			self.serverSend(command[0])

	def stopRun(self):
		self.autoWalkDirections = []
		return "Run canceled!"

	def sync(self, name=None, desc=None, exits=None, vnum=None):
		if vnum:
			if vnum in self.labels:
				vnum = self.labels[vnum]
			if vnum in self.rooms:
				self.prevRoom = self.rooms[vnum]
				self.currentRoom = self.rooms[vnum]
				self.isSynced = True
				self.clientSend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
			else:
				self.clientSend("No such vnum or label: {0}.".format(vnum))
		else:
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
		return self.isSynced

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

	def updateCurrentRoom(self, roomDict):
		output = []
		if self.autoUpdating:
			if roomDict["name"] and self.currentRoom.name != roomDict["name"]:
				self.currentRoom.name = roomDict["name"]
				output.append("Updating room name.")
			if roomDict["description"] and self.currentRoom.desc != roomDict["description"]:
				self.currentRoom.desc = roomDict["description"]
				output.append("Updating room description.")
			if roomDict["dynamic"] and self.currentRoom.dynamicDesc != roomDict["dynamic"]:
				self.currentRoom.dynamicDesc = roomDict["dynamic"]
				output.append("Updating room dynamic description.")
		try:
			light = LIGHT_SYMBOLS[roomDict["light"]]
			if light == "lit" and self.currentRoom.light != light:
				output.append(self.rlight("lit"))
		except KeyError:
			pass
		try:
			terrain = TERRAIN_SYMBOLS[roomDict["terrain"]]
			if self.currentRoom.terrain not in (terrain, "random", "death"):
				self.currentRoom.cost = TERRAIN_COSTS[terrain] if terrain in TERRAIN_COSTS else TERRAIN_COSTS["undefined"]
				output.append(self.rterrain(terrain))
		except KeyError:
			pass
		try:
			ridable = "r" in roomDict["movementFlags"].lower()
			if ridable and self.currentRoom.ridable != "ridable":
				output.append(self.rridable("ridable"))
		except KeyError:
			pass
		if roomDict["exits"]:
			exitsOutput = []
			for door, road, climb, portal, direction in EXIT_TAGS_REGEX.findall(roomDict["exits"]):
				# Portals aren't real exits.
				if portal:
					continue
				if direction not in self.currentRoom.exits:
					output.append("Adding exit '%s' to current room." % direction)
					self.currentRoom.exits[direction] = Exit()
					if self.autoLinking:
						vnums = [vnum for vnum, roomObj in iterItems(self.rooms) if self.coordinatesAddDirection((self.currentRoom.x, self.currentRoom.y, self.currentRoom.z), direction) == (roomObj.x, roomObj.y, roomObj.z)]
						if len(vnums) == 1 and REVERSE_DIRECTIONS[direction] in self.rooms[vnums[0]].exits and self.rooms[vnums[0]].exits[REVERSE_DIRECTIONS[direction]].to == "undefined":
							output.append(self.rlink("add %s %s" % (vnums[0], direction)))
				roomExit = self.currentRoom.exits[direction]
				if door and "door" not in roomExit.exitFlags:
					output.append(self.exitflags("add door %s" % direction))
				if road and "road" not in roomExit.exitFlags:
					output.append(self.exitflags("add road %s" % direction))
				if climb and "climb" not in roomExit.exitFlags:
					output.append(self.exitflags("add climb %s" % direction))
				if exitsOutput:
					exitsOutput.insert(0, "Exit %s:" % direction)
					output.extend(exitsOutput)
					del exitsOutput[:]
		if output:
			return self.clientSend("\n".join(output))

	def run(self):
		mpiThreads = []
		stripper = TelnetStripper()
		while True:
			isFromClient, data = self.mapperQueue.get()
			if data is None:
				break
			if isFromClient:
				# The data was sent from the user's mud client.
				matchedUserInput = USER_COMMANDS_REGEX.match(data)
				if matchedUserInput:
					# The data was a valid mapper command.
					getattr(self, "user_command_{0}".format(decodeBytes(matchedUserInput.group("command"))))(decodeBytes(matchedUserInput.group("arguments")))
				continue
			# The data was from the mud server.
			data = stripper.process(data)
			if data is None:
				# Keep buffering until IAC_GA is received.
				continue
			mpiMatch = MPI_REGEX.search(b"".join(data.lstrip().splitlines(True)))
			if mpiMatch is not None:
				# A local editing session was initiated.
				mpiThreads.append(MPI(client=self._client, server=self._server, isTinTin=self.isTinTin, mpiMatch=mpiMatch.groupdict()))
				mpiThreads[-1].start()
				continue
			data = MAPPER_IGNORE_TAGS_REGEX.sub(b"", data)
			data = ANSI_COLOR_REGEX.sub(b"", data)
			data = decodeBytes(multiReplace(data, XML_UNESCAPE_PATTERNS))
			if "<prompt>" in data and "</prompt>" in data:
				self.lastPrompt = data.rsplit("<prompt>", 1)[-1].rsplit("</prompt>", 1)[0]
			movementForcedSearch = MOVEMENT_FORCED_REGEX.search(data)
			if movementForcedSearch or MOVEMENT_PREVENTED_REGEX.search(data):
				self.stopRun()
			if self.isSynced:
				if movementForcedSearch is not None:
					if movementForcedSearch.group("ignore"):
						# Forced movement that is marked with 'ignore' indicates that the mapper should undo the last move and remain in sync.
						# This is used in situations such as a clump of roots pulling the player back into the room that he/she just left.
						self.currentRoom = self.rooms[self.prevRoom.vnum]
						self.clientSend("Forced movement ignored, still synced.")
						continue
					else:
						# The player was forcibly moved in an unknown direction.
						self.isSynced = False
						self.clientSend("Forced movement, no longer synced.")
				if self.autoMapping:
					if "It's too difficult to ride here." in data and self.currentRoom.ridable != "notridable":
						self.clientSend(self.rridable("notridable"))
					elif "You are already riding." in data and self.currentRoom.ridable != "ridable":
						self.clientSend(self.rridable("ridable"))
			try:
				roomDict = ROOM_TAGS_REGEX.search(data).groupdict()
			except AttributeError:
				continue
			# Room data was received
			if roomDict["movement"] and self.isSynced:
				# The player has moved in an existing direction, and has entered an existing room in the database. Adjust the map accordingly.
				if self.autoMapping and roomDict["movementDir"] and (roomDict["movementDir"] not in self.currentRoom.exits or self.currentRoom.exits[roomDict["movementDir"]].to not in self.rooms):
					if self.autoMerging:
						foundRooms = self.searchRooms(exactMatch=True, name=roomDict["name"], desc=roomDict["description"]) if roomDict["name"] and roomDict["description"] else []
					if self.autoMerging and len(foundRooms) == 1:
						output = []
						vnum, roomObj = foundRooms[0]
						if self.autoLinking and REVERSE_DIRECTIONS[roomDict["movementDir"]] in roomObj.exits and roomObj.exits[REVERSE_DIRECTIONS[roomDict["movementDir"]]].to == "undefined":
							output.append(self.rlink("add %s %s" % (vnum, roomDict["movementDir"])))
						else:
							output.append(self.rlink("add oneway %s %s" % (vnum, roomDict["movementDir"])))
						output.append("Auto Merging '%s' with name '%s'." % (vnum, roomObj.name))
						self.clientSend("\n".join(output))
					else:
						vnum = self.getNewVnum()
						newRoom = Room(vnum)
						newRoom.name = roomDict["name"] if roomDict["name"] else ""
						newRoom.desc = roomDict["description"] if roomDict["description"] else ""
						newRoom.dynamicDesc = roomDict["dynamic"] if roomDict["dynamic"] else ""
						newRoom.x, newRoom.y, newRoom.z = self.coordinatesAddDirection((self.currentRoom.x, self.currentRoom.y, self.currentRoom.z), roomDict["movementDir"])
						if REVERSE_DIRECTIONS[roomDict["movementDir"]] in roomDict["exits"]:
							newRoom.exits[REVERSE_DIRECTIONS[roomDict["movementDir"]]] = Exit()
							newRoom.exits[REVERSE_DIRECTIONS[roomDict["movementDir"]]].to = self.currentRoom.vnum
						self.clientSend("Adding room '%s' with vnum '%s'" % (newRoom.name, vnum))
						self.rooms[vnum] = newRoom
						self.currentRoom.exits[roomDict["movementDir"]].to = vnum
				self.move(roomDict["movementDir"])
				if self.autoWalkDirections:
					# The player is auto-walking. Send the next direction to Mume.
					self.walkNextDirection()
			# If necessary, try to sync the map to the current room.
			if roomDict["name"] in ("You just see a dense fog around you...", "It is pitch black...") or not self.isSynced and not self.sync(roomDict["name"]):
				# The room is dark, foggy, or the mapper was unable to sync to the current room.
				continue
			# The map is now synced.
			if self.autoMapping:
				# If necessary, update the current room's information in the database with the information received from Mume.
				self.updateCurrentRoom(roomDict)
		# end while, mapper thread ending.
		# Join the MPI threads (if any) before joining the Mapper thread.
		for mpiThread in mpiThreads:
			mpiThread.join()
		self.clientSend("Exiting mapper thread.")


class Proxy(threading.Thread):
	def __init__(self, client, server, mapperQueue):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self._mapperQueue = mapperQueue
		self.alive = threading.Event()

	def close(self):
		self.alive.clear()

	def run(self):
		self.alive.set()
		while self.alive.isSet():
			try:
				data = self._client.recv(4096)
			except socket.timeout:
				continue
			except IOError:
				self.close()
				continue
			if not data:
				self.close()
				continue
			elif USER_COMMANDS_REGEX.match(data):
				# True tells the mapper thread that the data is from the user's Mud client.
				self._mapperQueue.put((True, data))
				continue
			self._server.sendall(data)


class Server(threading.Thread):
	def __init__(self, client, server, mapperQueue, isTinTin=None):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self._mapperQueue = mapperQueue
		self.isTinTin = bool(isTinTin)

	def upperMatch(self, match):
		return b"".join((match.group("tag").upper(), b":", match.group("text").replace(b"\r\n", b"\n").replace(b"\n", b" ").strip() if match.group("text") else b"", b":", match.group("tag").upper(), b"\r\n" if match.group("tag") != b"prompt" else b""))

	def run(self):
		initialOutput = b"".join((IAC, DO, TTYPE, IAC, DO, NAWS))
		encounteredInitialOutput = False
		while True:
			data = self._server.recv(4096)
			if not data:
				break
			elif not encounteredInitialOutput and data.startswith(initialOutput):
				# Identify for Mume Remote Editing.
				if sys.platform != "win32":
					self._server.sendall(b"~$#EI\n")
				# Turn on XML mode.
				self._server.sendall(b"~$#EX1\n3\n")
				# Tell the Mume server to put IAC-GA at end of prompts.
				self._server.sendall(b"~$#EP2\nG\n")
				encounteredInitialOutput = True
			# False tells the mapper thread that the data is from the Mume server, and *not* from the user's Mud client.
			self._mapperQueue.put((False, data))
			if self.isTinTin:
				data = TINTIN_IGNORE_TAGS_REGEX.sub(b"", data)
				data = TINTIN_SEPARATE_TAGS_REGEX.sub(self.upperMatch, data)
				data = multiReplace(data, XML_UNESCAPE_PATTERNS)
			self._client.sendall(data)


def main(isTinTin=None):
	proxySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	proxySocket.bind(("", 4000))
	proxySocket.listen(1)
	clientConnection, proxyAddress = proxySocket.accept()
	clientConnection.settimeout(1.0)
	serverConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serverConnection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
	try:
		serverConnection.connect(("193.134.218.99", 4242))
	except TimeoutError:
		clientConnection.sendall(b"\r\nError: server connection timed out!\r\n")
		try:
			clientConnection.sendall(b"\r\n")
			clientConnection.shutdown(socket.SHUT_RDWR)
		except:
			pass
		clientConnection.close()
		return
	mapperQueue = Queue()
	mapperThread = Mapper(client=clientConnection, server=serverConnection, mapperQueue=mapperQueue, isTinTin=isTinTin)
	proxyThread = Proxy(client=clientConnection, server=serverConnection, mapperQueue=mapperQueue)
	serverThread = Server(client=clientConnection, server=serverConnection, mapperQueue=mapperQueue, isTinTin=isTinTin)
	serverThread.start()
	proxyThread.start()
	mapperThread.start()
	serverThread.join()
	try:
		serverConnection.shutdown(socket.SHUT_RDWR)
	except:
		pass
	mapperQueue.put((None, None))
	mapperThread.join()
	try:
		clientConnection.sendall(b"\r\n")
		proxyThread.close()
		clientConnection.shutdown(socket.SHUT_RDWR)
	except:
		pass
	proxyThread.join()
	serverConnection.close()
	clientConnection.close()
