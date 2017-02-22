# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import re
from telnetlib import IAC
import threading
from timeit import default_timer

from .config import Config, config_lock
from .constants import DIRECTIONS, REVERSE_DIRECTIONS, RUN_DESTINATION_REGEX, USER_COMMANDS_REGEX, EXIT_TAGS_REGEX, ANSI_COLOR_REGEX, MOVEMENT_FORCED_REGEX, MOVEMENT_PREVENTED_REGEX, TERRAIN_COSTS, TERRAIN_SYMBOLS, LIGHT_SYMBOLS, PROMPT_REGEX, XML_UNESCAPE_PATTERNS
from .world import Room, Exit, World
from .utils import iterItems, decodeBytes, regexFuzzy, simplified, multiReplace

USER_DATA = 0
MUD_DATA = 1

class Mapper(threading.Thread, World):
	def __init__(self, client, server, use_gui):
		threading.Thread.__init__(self)
		self.name = "Mapper"
		# Initialize the timer.
		self.initTimer = default_timer()
		self._client = client
		self._server = server
		self.queue = Queue()
		self.autoMapping = False
		self.autoUpdating = False
		self.autoMerging = True
		self.autoLinking = True
		self.autoWalkDirections = []
		self.lastPathFindQuery = ""
		World.__init__(self, use_gui=use_gui)

	def output(self, text):
		# Override World.output.
		return self.clientSend(text)

	def clientSend(self, msg):
		self._client.sendall(msg.encode("utf-8").replace(IAC, IAC+IAC) + b"\r\n")
		return None

	def serverSend(self, msg):
		self._server.sendall(msg.encode("utf-8").replace(IAC, IAC + IAC) + b"\r\n")
		return None

	def user_command_gettimer(self, *args):
		self.clientSend("TIMER:%d:TIMER" % int(default_timer() - self.initTimer))

	def user_command_gettimerms(self, *args):
		self.clientSend("TIMERMS:%d:TIMERMS" % int((default_timer() - self.initTimer) * 1000))

	def user_command_secretaction(self, *args):
		regex = re.compile(r"^\s*(?P<action>.+?)(?:\s+(?P<direction>%s))?$" % regexFuzzy(DIRECTIONS))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return self.clientSend("Syntax: 'secretaction [action] [%s]'." % " | ".join(DIRECTIONS))
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"])) if matchDict["direction"] else ""
		door = self.currentRoom.exits[direction].door if direction and direction in self.currentRoom.exits and self.currentRoom.exits[direction].door else "exit"
		return self.serverSend(" ".join(item for item in (matchDict["action"], door, direction[0:1]) if item))

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

	def user_command_ravoid(self, *args):
		self.clientSend(self.ravoid(*args))

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

	def user_command_vnum(self, *args):
		self.clientSend(self.currentRoom.vnum)

	def user_command_tvnum(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.clientSend("Tell VNum to who?")
		else:
			self.serverSend("tell %s %s" % (args[0].strip(), self.currentRoom.vnum))

	def user_command_rlabel(self, *args):
		result = self.rlabel(*args)
		if result:
			self.clientSend("\r\n".join(result))

	def user_command_savemap(self, *args):
		self.saveRooms()

	def user_command_run(self, *args):
		if not args or not args[0] or not args[0].strip():
			return self.clientSend("Usage: run [label|vnum]")
		self.autoWalkDirections = []
		argString = args[0].strip()
		if argString.lower() == "c":
			if self.lastPathFindQuery:
				match = RUN_DESTINATION_REGEX.match(self.lastPathFindQuery)
				destination = match.group("destination")
				self.clientSend(destination)
			else:
				return self.clientSend("Error: no previous path to continue.")
		elif argString.lower() == "t" or argString.lower().startswith("t "):
			argString = argString[2:].strip()
			if not argString:
				if self.lastPathFindQuery:
					return self.clientSend("Run target set to '%s'. Use 'run t [rlabel|vnum]' to change it." % self.lastPathFindQuery)
				else:
					return self.clientSend("Please specify a VNum or room label to target.")
			self.lastPathFindQuery = argString
			return self.clientSend("Setting run target to '%s'" % self.lastPathFindQuery)
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

	def user_command_path(self, *args):
		if not args or not args[0]:
			return self.clientSend("Usage: run [label|vnum]")
		argString = args[0].strip()
		match = RUN_DESTINATION_REGEX.match(argString)
		destination = match.group("destination")
		flags = match.group("flags")
		if flags:
			flags = flags.split("|")
		else:
			flags = None
		result = self.pathFind(destination=destination, flags=flags)
		if result is not None:
			self.clientSend(self.createSpeedWalk(result))

	def user_command_sync(self, *args):
		if not args or not args[0]:
			self.clientSend("Map no longer synced. Auto sync on.")
			self.isSynced = False
			self.serverSend("look")
		else:
			self.sync(vnum=args[0].strip())

	def walkNextDirection(self):
		if not self.autoWalkDirections:
			return
		while self.autoWalkDirections:
			command = self.autoWalkDirections.pop()
			if not self.autoWalkDirections:
				self.clientSend("Arriving at destination.")
			if command in DIRECTIONS:
				# Send the first character of the direction to Mume.
				self.serverSend(command[0])
				break
			else:
				# command is a non-direction such as 'lead' or 'ride'.
				self.serverSend(command)

	def stopRun(self):
		self.autoWalkDirections = []
		return "Run canceled!"

	def sync(self, name=None, desc=None, exits=None, vnum=None):
		if vnum:
			if vnum in self.labels:
				vnum = self.labels[vnum]
			if vnum in self.rooms:
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
				self.currentRoom = self.rooms[vnums[0]]
				self.isSynced = True
				self.clientSend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
			else:
				self.clientSend("More than one room in the database matches current room. Unable to sync.")
		return self.isSynced

	def roomDetails(self):
		doors = []
		deathTraps = []
		oneWays = []
		undefineds = []
		for direction, exitObj in iterItems(self.currentRoom.exits):
			if exitObj.door and exitObj.door != "exit":
				doors.append("%s: %s" % (direction, exitObj.door))
			if not exitObj.to or exitObj.to == "undefined":
				undefineds.append(direction)
			elif exitObj.to == "death":
				deathTraps.append(direction)
			elif REVERSE_DIRECTIONS[direction] not in self.rooms[exitObj.to].exits or self.rooms[exitObj.to].exits[REVERSE_DIRECTIONS[direction]].to != self.currentRoom.vnum:
				oneWays.append(direction)
		if doors:
			self.clientSend("Doors: %s" % ", ".join(doors))
		if deathTraps:
			self.clientSend("Death Traps: %s" % ", ".join(deathTraps))
		if oneWays:
			self.clientSend("One ways: %s" % ", ".join(oneWays))
		if undefineds:
			self.clientSend("Undefineds: %s" % ", ".join(undefineds))
		if self.currentRoom.note:
			self.clientSend("Note: %s" % self.currentRoom.note)

	def updateRoomFlags(self, prompt):
		match = PROMPT_REGEX.search(prompt)
		if not match:
			return
		promptDict = match.groupdict()
		output = []
		try:
			light = LIGHT_SYMBOLS[promptDict["light"]]
			if light == "lit" and self.currentRoom.light != light:
				output.append(self.rlight("lit"))
		except KeyError:
			pass
		try:
			terrain = TERRAIN_SYMBOLS[promptDict["terrain"]]
			if self.currentRoom.terrain not in (terrain, "random", "death"):
				output.append(self.rterrain(terrain))
		except KeyError:
			pass
		try:
			ridable = "r" in promptDict["movementFlags"].lower()
			if ridable and self.currentRoom.ridable != "ridable":
				output.append(self.rridable("ridable"))
		except KeyError:
			pass
		if output:
			return self.clientSend("\n".join(output))

	def updateExitFlags(self, exits):
		if not exits:
			return
		output = []
		exitsOutput = []
		for door, road, climb, portal, direction in EXIT_TAGS_REGEX.findall(exits):
			# Portals aren't real exits.
			if portal:
				continue
			if direction not in self.currentRoom.exits:
				output.append("Adding exit '%s' to current room." % direction)
				self.currentRoom.exits[direction] = self.getNewExit(direction)
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

	def autoMergeRoom(self, movement, vnum, roomObj):
		output = []
		if self.autoLinking and REVERSE_DIRECTIONS[movement] in roomObj.exits and roomObj.exits[REVERSE_DIRECTIONS[movement]].to == "undefined":
			output.append(self.rlink("add %s %s" % (vnum, movement)))
		else:
			output.append(self.rlink("add oneway %s %s" % (vnum, movement)))
		output.append("Auto Merging '%s' with name '%s'." % (vnum, roomObj.name))
		return self.clientSend("\n".join(output))

	def addNewRoom(self, movement, name, description, dynamic):
		vnum = self.getNewVnum()
		newRoom = Room(vnum)
		newRoom.name = name
		newRoom.desc = description
		newRoom.dynamicDesc = dynamic
		newRoom.x, newRoom.y, newRoom.z = self.coordinatesAddDirection((self.currentRoom.x, self.currentRoom.y, self.currentRoom.z), movement)
		self.rooms[vnum] = newRoom
		if movement not in self.currentRoom.exits:
			self.currentRoom.exits[movement] = self.getNewExit(movement)
		self.currentRoom.exits[movement].to = vnum
		self.clientSend("Adding room '%s' with vnum '%s'" % (newRoom.name, vnum))

	def run(self):
		addedNewRoom = False
		scouting = False
		movement = None
		prompt = ""
		name = ""
		description = ""
		dynamic = ""
		exits = ""
		queue = self.queue
		while True:
			dataType, data = queue.get()
			if data is None:
				break
			elif dataType == USER_DATA:
				# The data was sent from the user's mud client.
				matchedUserInput = USER_COMMANDS_REGEX.match(data)
				if matchedUserInput:
					# The data was a valid mapper command.
					getattr(self, "user_command_{0}".format(decodeBytes(matchedUserInput.group("command"))))(decodeBytes(matchedUserInput.group("arguments")))
				continue
			# The data was from the mud server.
			event, data = data
			data = ANSI_COLOR_REGEX.sub("", simplified(decodeBytes(multiReplace(data, XML_UNESCAPE_PATTERNS))))
			if event == "movement":
				movement = data
				scouting = False
			elif scouting and event != "prompt":
				# Ignore room data received by scouting.
				continue
			elif event == "misc":
				if "You quietly scout " in data:
					scouting = True
					continue
				if "Wet, cold and filled with mud you drop down into a dark and moist cave, while you notice the mud above you moving to close the hole you left in the cave ceiling." in data:
					self.sync(vnum="17189")
				if MOVEMENT_FORCED_REGEX.search(data) or MOVEMENT_PREVENTED_REGEX.search(data):
					self.stopRun()
				if self.isSynced and self.autoMapping:
					if "It's too difficult to ride here." in data and self.currentRoom.ridable != "notridable":
						self.clientSend(self.rridable("notridable"))
					elif "You are already riding." in data and self.currentRoom.ridable != "ridable":
						self.clientSend(self.rridable("ridable"))
			elif event == "name":
				name = data if data not in ("You just see a dense fog around you...", "It is pitch black...") else ""
			elif event == "description":
				description = data
			elif event == "dynamic":
				dynamic = data
				if self.autoMapping and self.isSynced:
					if movement in DIRECTIONS and (movement not in self.currentRoom.exits or self.currentRoom.exits[movement].to not in self.rooms):
						# Player has moved in a direction that either doesn't exist in the database or links to an invalid vnum (E.G. undefined).
						if self.autoMerging and name and description:
							duplicateRooms = self.searchRooms(exactMatch=True, name=name, desc=description)
						else:
							duplicateRooms = None
						if not name:
							self.clientSend("Unable to add new room: empty room name.")
						elif not description:
							self.clientSend("Unable to add new room: empty room description.")
						elif duplicateRooms and len(duplicateRooms) == 1:
							vnum, roomObj = duplicateRooms[0]
							self.autoMergeRoom(movement, vnum, roomObj)
						else:
							# Create new room.
							self.addNewRoom(movement, name, description, dynamic)
							addedNewRoom = True
			elif event == "exits":
				exits = data
				if addedNewRoom and REVERSE_DIRECTIONS[movement] in exits:
					newRoom = self.rooms[self.currentRoom.exits[movement].to]
					newRoom.exits[REVERSE_DIRECTIONS[movement]] = self.getNewExit(REVERSE_DIRECTIONS[movement], self.currentRoom.vnum)
				addedNewRoom = False
			elif event == "prompt":
				prompt = data
				if movement is not None and self.isSynced:
					if not movement:
						# The player was forcibly moved in an unknown direction.
						self.isSynced = False
						self.clientSend("Forced movement, no longer synced.")
					elif movement not in DIRECTIONS:
						self.isSynced = False
						self.clientSend("Error: Invalid direction '{0}'. Map no longer synced!".format(movement))
					elif movement not in self.currentRoom.exits:
						self.isSynced = False
						self.clientSend("Error: direction '{0}' not in database. Map no longer synced!".format(movement))
					elif self.currentRoom.exits[movement].to not in self.rooms:
						self.isSynced = False
						self.clientSend("Error: vnum ({0}) in direction ({1}) is not in the database. Map no longer synced!".format(self.currentRoom.exits[movement].to, movement))
					else:
						self.currentRoom = self.rooms[self.currentRoom.exits[movement].to]
						if self.autoMapping:
							if self.autoUpdating and name and self.currentRoom.name != name:
								self.currentRoom.name = name
								self.clientSend("Updating room name.")
							if self.autoUpdating and description and self.currentRoom.desc != description:
								self.currentRoom.desc = description
								self.clientSend("Updating room description.")
							if self.autoUpdating and dynamic and self.currentRoom.dynamicDesc != dynamic:
								self.currentRoom.dynamicDesc = dynamic
								self.clientSend("Updating room dynamic description.")
							self.updateExitFlags(exits)
							self.updateRoomFlags(prompt)
					if self.autoWalkDirections:
						# The player is auto-walking. Send the next direction to Mume.
						self.walkNextDirection()
				if name:
					if self.isSynced or self.sync(name):
						self.roomDetails()
				addedNewRoom = False
				scouting = False
				movement = None
				prompt = ""
				name = ""
				description = ""
				dynamic = ""
				exits = ""
		# end while, mapper thread ending.
		self.clientSend("Exiting mapper thread.")
