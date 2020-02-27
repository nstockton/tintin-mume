# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import logging
try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import re
from telnetlib import IAC
import textwrap
import threading
from timeit import default_timer

from . import roomdata
from .cleanmap import ExitsCleaner
from .clock import (
	CLOCK_REGEX,
	TIME_REGEX,
	DAWN_REGEX,
	DAY_REGEX,
	DUSK_REGEX,
	NIGHT_REGEX,
	MONTHS,
	timeToEpoch,
	Clock
)
from .config import Config, config_lock
from .timers import Timer
from .world import (
	DIRECTIONS,
	REVERSE_DIRECTIONS,
	LIGHT_SYMBOLS,
	TERRAIN_SYMBOLS,
	RUN_DESTINATION_REGEX,
	World
)
from .utils import formatDocString, stripAnsi, decodeBytes, regexFuzzy, simplified, escapeXML, unescapeXML


EXIT_TAGS_REGEX = re.compile(
	r"(?P<door>[\(\[\#]?)(?P<road>[=-]?)(?P<climb>[/\\]?)(?P<portal>[\{{]?)(?P<direction>{dirs})".format(
		dirs="|".join(DIRECTIONS)
	)
)
MOVEMENT_FORCED_REGEX = re.compile(
	"|".join(
		[
			r"You feel confused and move along randomly\.\.\.",
			r"Suddenly an explosion of ancient rhymes makes the space collapse around you\!",
			r"The pain stops\, your vision clears\, and you realize that you are elsewhere\.",
			r"A guard leads you out of the house\.",
			r"You leave the ferry\.",
			r"You reached the riverbank\.",
			r"You stop moving towards the (?:left|right) bank and drift downstream\.",
			r"You are borne along by a strong current\.",
			r"You are swept away by the current\.",
			r"You are swept away by the powerful current of water\.",
			r"You board the ferry\.",
			r"You are dead\! Sorry\.\.\.",
			r"With a jerk\, the basket starts gliding down the rope towards the platform\.",
			r"The current pulls you faster\. Suddenly\, you are sucked downwards into darkness\!",
			r"You are washed blindly over the rocks\, and plummet sickeningly downwards\.\.\.",
			r"Oops\! You walk off the bridge and fall into the rushing water below\!",
			r"Holding your breath and with closed eyes\, you are squeezed below the surface of the water\.",
			r"You tighten your grip as (:a Great Eagle|Gwaihir the Windlord) starts to descend fast\.",
			r"The trees confuse you\, making you wander around in circles\.",
			r"Sarion helps you outside\.",
			(
				r"You cannot control your mount on the slanted and unstable surface\!"
				r"(?: You begin to slide to the north\, and plunge toward the water below\!)?"
			),
			(
				r"Stepping on the lizard corpses\, you use some depressions in the wall for support\, "
				r"push the muddy ceiling apart and climb out of the cave\."
			)
		]
	)
)
MOVEMENT_PREVENTED_REGEX = re.compile(
	"^(?:{lines})$".format(
		lines="|".join(
			[
				r"The \w+ seem[s]? to be closed\.",
				r"It seems to be locked\.",
				r"You cannot ride there\.",
				r"Your boat cannot enter this place\.",
				r"A guard steps in front of you\.",
				r"The clerk bars your way\.",
				r"You cannot go that way\.\.\.",
				r"Alas\, you cannot go that way\.\.\.",
				r"You need to swim to go there\.",
				r"You failed swimming there\.",
				r"You failed to climb there and fall down\, hurting yourself\.",
				r"Your mount cannot climb the tree\!",
				r"No way\! You are fighting for your life\!",
				r"In your dreams\, or what\?",
				r"You are too exhausted\.",
				r"You unsuccessfully try to break through the ice\.",
				r"Your mount refuses to follow your orders\!",
				r"You are too exhausted to ride\.",
				r"You can\'t go into deep water\!",
				r"You don\'t control your mount\!",
				r"Your mount is too sensible to attempt such a feat\.",
				r"Oops\! You cannot go there riding\!",
				r"You\'d better be swimming if you want to dive underwater\.",
				r"You need to climb to go there\.",
				r"You cannot climb there\.",
				r"If you still want to try\, you must \'climb\' there\.",
				r"Nah\.\.\. You feel too relaxed to do that\.",
				r"Maybe you should get on your feet first\?",
				r"Not from your present position\!",
				(
					r".+ (?:prevents|keeps) you from going "
					r"(?:north|south|east|west|up|down|upstairs|downstairs|past (?:him|her|it))\."
				),
				(
					r"A (?:pony|dales-pony|horse|warhorse|pack horse|trained horse|"
					r"horse of the Rohirrim|brown donkey|mountain mule|hungry warg|brown wolf)"
					r"(?: \(\w+\))? (?:is too exhausted|doesn't want you riding (?:him|her|it) anymore)\."
				)
			]
		)
	)
)
PROMPT_REGEX = re.compile(
	(
		r"^(?P<light>[@*!\)o]?)(?P<terrain>[\#\(\[\+\.%fO~UW:=<]?)"
		r"(?P<weather>[*'\"~=-]{0,2})\s*(?P<movementFlags>[RrSsCcW]{0,4})[^\>]*\>$"
	)
)
USER_DATA = 0
MUD_DATA = 1


logger = logging.getLogger(__name__)


class Mapper(threading.Thread, World):
	def __init__(
			self,
			client,
			server,
			outputFormat,
			interface,
			promptTerminator,
			gagPrompts,
			findFormat,
			isEmulatingOffline
	):
		threading.Thread.__init__(self)
		self.name = "Mapper"
		# Initialize the timer.
		self.initTimer = default_timer()
		self._client = client
		self._server = server
		self._outputFormat = outputFormat
		self._promptTerminator = promptTerminator
		self.gagPrompts = gagPrompts
		self.findFormat = findFormat
		self.isEmulatingOffline = isEmulatingOffline
		self.queue = Queue()
		with config_lock:
			cfg = Config()
			self._autoUpdateRooms = cfg.get("autoUpdateRooms", False)
			del cfg
		self.autoMapping = False
		self.autoMerging = True
		self.autoLinking = True
		self.autoWalk = False
		self.autoWalkDirections = []
		self.userCommands = [
			func[len("user_command_"):] for func in dir(self)
			if func and func.startswith("user_command_") and callable(self.__getattribute__(func))
		]
		self.mudEventHandlers = {}
		for legacyHandler in [
			func[len("mud_event_"):] for func in dir(self)
			if func and func.startswith("mud_event_") and callable(self.__getattribute__(func))
		]:
			self.registerMudEventHandler(legacyHandler, getattr(self, "mud_event_" + legacyHandler))
		self.unknownMudEvents = []
		ExitsCleaner(self, "exits")
		self.emulationCommands = [
			func[len("emulation_command_"):] for func in dir(self)
			if func and func.startswith("emulation_command_") and callable(self.__getattribute__(func))
		]
		priorityCommands = [  # commands that should have priority when matching user input to an emulation command
			"exits"
		]
		self.emulationCommands.sort(
			key=lambda command: (
				# Sort emulation commands with prioritized commands at the top, alphabetically otherwise.
				priorityCommands.index(command) if command in priorityCommands else len(priorityCommands),
				command
			)
		)
		self.isEmulatingBriefMode = True
		self.lastPathFindQuery = ""
		self.prompt = ""
		self.clock = Clock()
		self.addedNewRoomFrom = None
		self.scouting = False
		self.movement = None
		self.moved = None
		self.roomName = None
		self.description = None
		self.dynamic = None
		self.exits = None
		self.timeEvent = None
		self.timeEventOffset = 0
		self.parsedHour = 0
		self.parsedMinutes = 0
		self.timeSynchronized = False
		World.__init__(self, interface=interface)

	@property
	def autoUpdateRooms(self):
		return self._autoUpdateRooms

	@autoUpdateRooms.setter
	def autoUpdateRooms(self, value):
		self._autoUpdateRooms = bool(value)
		with config_lock:
			cfg = Config()
			cfg["autoUpdateRooms"] = self._autoUpdateRooms
			cfg.save()
			del cfg

	def output(self, *args, **kwargs):
		# Override World.output.
		return self.clientSend(*args, **kwargs)

	def clientSend(self, msg, showPrompt=True):
		if self._outputFormat == "raw":
			if showPrompt and self.prompt and not self.gagPrompts:
				self._client.sendall(
					"{msg}\r\n<prompt>{prompt}</prompt>".format(
						msg=escapeXML(msg),
						prompt=escapeXML(self.prompt)
					).encode("utf-8").replace(IAC, IAC + IAC) + self._promptTerminator
				)
			else:
				self._client.sendall(
					"\r\n{msg}\r\n".format(msg=escapeXML(msg)).encode("utf-8").replace(IAC, IAC + IAC)
				)
		elif self._outputFormat == "tintin":
			if showPrompt and self.prompt and not self.gagPrompts:
				self._client.sendall(
					"{msg}\r\nPROMPT:{prompt}:PROMPT".format(
						msg=msg,
						prompt=self.prompt
					).encode("utf-8").replace(IAC, IAC + IAC) + self._promptTerminator
				)
			else:
				self._client.sendall(
					"\r\n{msg}\r\n".format(msg=msg).encode("utf-8").replace(IAC, IAC + IAC)
				)
		else:
			if showPrompt and self.prompt and not self.gagPrompts:
				self._client.sendall(
					"{msg}\r\n{prompt}".format(
						msg=msg,
						prompt=self.prompt
					).encode("utf-8").replace(IAC, IAC + IAC) + self._promptTerminator
				)
			else:
				self._client.sendall(
					"\r\n{msg}\r\n".format(msg=msg).encode("utf-8").replace(IAC, IAC + IAC)
				)
		return None

	def serverSend(self, msg):
		self._server.sendall(msg.encode("utf-8").replace(IAC, IAC + IAC) + b"\r\n")
		return None

	def emulation_command_brief(self, *args):
		"""toggles brief mode."""
		self.isEmulatingBriefMode = not self.isEmulatingBriefMode
		self.output("Brief mode {}".format("on" if self.isEmulatingBriefMode else "off"))

	def emulation_command_examine(self, *args):
		"""shows the room's description."""
		self.output(self.emulationRoom.desc)

	def emulation_command_exits(self, *args):
		"""shows the exits in the room."""
		exits = [key for key in DIRECTIONS if key in self.emulationRoom.exits.keys()]
		self.output("Exits: {}.".format(", ".join(exits)))

	def emulation_command_go(self, label, isJump=True):
		"""mimic the /go command that the ainur use."""
		room, error = self.getRoomFromLabel(label)
		if error:
			self.output(error)
			return
		self.emulationRoom = room
		self.emulation_command_look()
		self.emulation_command_exits()
		if self.isEmulatingOffline:
			self.currentRoom = self.emulationRoom
		if isJump:
			self.lastEmulatedJump = room

	def emulation_command_help(self, *args):
		"""Shows documentation for mapper's emulation commands."""
		helpTexts = [
			(funcName, getattr(self, "emulation_command_" + funcName).__doc__)
			for funcName in self.emulationCommands
		]
		documentedFuncs = [
			(name, formatDocString(docString, prefix=" " * 8).strip()) for name, docString in helpTexts
			if docString.strip()
		]
		undocumentedFuncs = [text for text in helpTexts if not text[1].strip()]
		result = [
			"The following commands allow you to emulate exploring the map without needing to move in game:",
			"\n".join("    {}: {}".format(*helpText) for helpText in documentedFuncs)
		]
		if undocumentedFuncs:
			result.append("The following commands have no documentation yet.")
			result.append(
				textwrap.indent(
					textwrap.fill(
						", ".join(helpText[0] for helpText in undocumentedFuncs),
						width=79,
						break_long_words=False,
						break_on_hyphens=False
					),
					prefix="    "
				)
			)
		self.output("\n".join(result))

	def emulation_command_look(self, *args):
		"""looks at the room."""
		self.output(self.emulationRoom.name)
		if not self.isEmulatingBriefMode:
			self.output(self.emulationRoom.desc)
		self.output(self.emulationRoom.dynamicDesc)
		if self.emulationRoom.note:
			self.output("Note: {}".format(self.emulationRoom.note))

	def emulation_command_return(self, *args):
		"""returns to the last room jumped to with the go command."""
		if self.lastEmulatedJump:
			self.emulation_command_go(self.lastEmulatedJump)
		else:
			self.output("Cannot return anywhere until the go command has been used at least once.")

	def emulation_command_sync(self, *args):
		"""
		When emulating while connected to the mud, syncs the emulated location with the in-game location.
		When running in offline mode, is equivalent to the return command.
		"""
		if self.isEmulatingOffline:
			self.emulation_command_return()
		else:
			self.emulation_command_go(self.currentRoom)

	def emulate_leave(self, direction):
		"""emulates leaving the room into a neighbouring room"""
		if direction not in self.emulationRoom.exits:
			self.output("Alas, you cannot go that way...")
			return
		room = self.emulationRoom.exits[direction].to
		if "death" == room:
			self.output("deathtrap!")
		elif "undefined" == room:
			self.output("undefined")
		else:
			self.emulation_command_go(room, isJump=False)

	def user_command_emu(self, *args):
		inputText = args[0].split(" ")
		userCommand = inputText[0].lower()
		userArgs = " ".join(inputText[1:])
		if not userCommand:
			self.output("What command do you want to emulate?")
			return
		# get the full name of the user's command
		for command in DIRECTIONS + self.emulationCommands:
			if command.startswith(userCommand):
				if command in DIRECTIONS:
					self.emulate_leave(command)
				else:
					getattr(self, "emulation_command_" + command)(userArgs)
				return
		if userCommand in self.userCommands:
			# call the user command
			# first set current room to the emulation room so the user command acts on the emulation room
			oldRoom = self.currentRoom
			self.currentRoom = self.emulationRoom
			getattr(self, "user_command_" + userCommand)(userArgs)
			self.currentRoom = oldRoom
		elif userCommand:
			self.output("Invalid command. Type 'help' for more help.")

	def user_command_gettimer(self, *args):
		self.clientSend("TIMER:{:d}:TIMER".format(int(default_timer() - self.initTimer)))

	def user_command_gettimerms(self, *args):
		self.clientSend("TIMERMS:{:d}:TIMERMS".format(int((default_timer() - self.initTimer) * 1000)))

	def user_command_clock(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.clientSend(self.clock.time())
		else:
			self.serverSend(self.clock.time(args[0].strip().lower()))

	def user_command_secretaction(self, *args):
		regex = re.compile(r"^\s*(?P<action>.+?)(?:\s+(?P<direction>{}))?$".format(regexFuzzy(DIRECTIONS)))
		try:
			matchDict = regex.match(args[0].strip().lower()).groupdict()
		except (NameError, IndexError, AttributeError):
			return self.clientSend("Syntax: 'secretaction [action] [{}]'.".format(" | ".join(DIRECTIONS)))
		if matchDict["direction"]:
			direction = "".join(dir for dir in DIRECTIONS if dir.startswith(matchDict["direction"]))
		else:
			direction = ""
		if direction and direction in self.currentRoom.exits and self.currentRoom.exits[direction].door:
			door = self.currentRoom.exits[direction].door
		else:
			door = "exit"
		return self.serverSend(" ".join(item for item in (matchDict["action"], door, direction[0:1]) if item))

	def user_command_automap(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoMapping = not self.autoMapping
		else:
			self.autoMapping = args[0].strip().lower() == "on"
		self.clientSend("Auto Mapping {}.".format("on" if self.autoMapping else "off"))

	def user_command_autoupdate(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoUpdateRooms = not self.autoUpdateRooms
		else:
			self.autoUpdateRooms = args[0].strip().lower() == "on"
		self.clientSend("Auto update rooms {}.".format("on" if self.autoUpdateRooms else "off"))

	def user_command_automerge(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoMerging = not self.autoMerging
		else:
			self.autoMerging = args[0].strip().lower() == "on"
		self.clientSend("Auto Merging {}.".format("on" if self.autoMerging else "off"))

	def user_command_autolink(self, *args):
		if not args or not args[0] or not args[0].strip():
			self.autoLinking = not self.autoLinking
		else:
			self.autoLinking = args[0].strip().lower() == "on"
		self.clientSend("Auto Linking {}.".format("on" if self.autoLinking else "off"))

	def user_command_rdelete(self, *args):
		self.clientSend(self.rdelete(*args))

	def user_command_fdoor(self, *args):
		self.clientSend(self.fdoor(self.findFormat, *args))

	def user_command_fdynamic(self, *args):
		self.clientSend(self.fdynamic(self.findFormat, *args))

	def user_command_flabel(self, *args):
		self.clientSend(self.flabel(self.findFormat, *args))

	def user_command_fname(self, *args):
		self.clientSend(self.fname(self.findFormat, *args))

	def user_command_fnote(self, *args):
		self.clientSend(self.fnote(self.findFormat, *args))

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
		"""states the vnum of the current room"""
		self.clientSend("Vnum: {}.".format(self.currentRoom.vnum))

	def user_command_tvnum(self, *args):
		"""tells a given char the vnum of your room"""
		if not args or not args[0] or not args[0].strip():
			self.clientSend("Tell VNum to who?")
		else:
			self.serverSend("tell {} {}".format(args[0].strip(), self.currentRoom.vnum))

	def user_command_rlabel(self, *args):
		result = self.rlabel(*args)
		if result:
			self.clientSend("\r\n".join(result))

	def user_command_getlabel(self, *args):
		self.clientSend(self.getlabel(*args))

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
					return self.clientSend(
						"Run target set to '{}'. Use 'run t [rlabel|vnum]' to change it.".format(
							self.lastPathFindQuery
						)
					)
				else:
					return self.clientSend("Please specify a VNum or room label to target.")
			self.lastPathFindQuery = argString
			return self.clientSend("Setting run target to '{}'".format(self.lastPathFindQuery))
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
			self.autoWalk = True
			if result:
				if argString != "c":
					self.lastPathFindQuery = argString
				self.walkNextDirection()

	def user_command_step(self, *args):
		if not args or not args[0] or not args[0].strip():
			return self.clientSend("Usage: step [label|vnum]")
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
			self.autoWalkDirections = result
			self.walkNextDirection()
		else:
			self.clientSend("Specify a path to follow.")

	def user_command_stop(self, *args):
		self.clientSend(self.stopRun())

	def user_command_path(self, *args):
		result = self.path(*args)
		if result is not None:
			self.clientSend(result)

	def user_command_sync(self, *args):
		if not args or not args[0]:
			self.clientSend("Map no longer synced. Auto sync on.")
			self.isSynced = False
			self.serverSend("look")
		else:
			self.sync(vnum=args[0].strip())

	def user_command_maphelp(self, *args):
		"""Shows documentation for mapper commands"""
		helpTexts = [
			(funcName, getattr(self, "user_command_" + funcName).__doc__ or "")
			for funcName in self.userCommands
		]
		documentedFuncs = [
			(name, formatDocString(docString, prefix=" " * 8).strip()) for name, docString in helpTexts
			if docString.strip()
		]
		undocumentedFuncs = [text for text in helpTexts if not text[1].strip()]
		result = [
			"Mapper Commands",
			"The following commands are used for viewing and editing map data:",
			"\n".join("    {}: {}".format(*helpText) for helpText in documentedFuncs)
		]
		if undocumentedFuncs:
			result.append("Undocumented Commands:")
			result.append(
				textwrap.indent(
					textwrap.fill(
						", ".join(helpText[0] for helpText in undocumentedFuncs),
						width=79,
						break_long_words=False,
						break_on_hyphens=False
					),
					prefix="    "
				)
			)
		self.output("\n".join(result))

	def walkNextDirection(self):
		if not self.autoWalkDirections:
			return
		while self.autoWalkDirections:
			command = self.autoWalkDirections.pop()
			if not self.autoWalkDirections:
				self.clientSend("Arriving at destination.")
				self.autoWalk = False
			if command in DIRECTIONS:
				# Send the first character of the direction to Mume.
				self.serverSend(command[0])
				break
			else:
				# command is a non-direction such as 'lead' or 'ride'.
				self.serverSend(command)

	def stopRun(self):
		self.autoWalk = False
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
			nameVnums = []
			descVnums = []
			for vnum, roomObj in self.rooms.items():
				if roomObj.name == name:
					nameVnums.append(vnum)
				if desc and roomObj.desc == desc:
					descVnums.append(vnum)
			if not nameVnums:
				self.clientSend("Current room not in the database. Unable to sync.")
			elif len(descVnums) == 1:
				self.currentRoom = self.rooms[descVnums[0]]
				self.isSynced = True
				self.clientSend("Synced to room {0} with vnum {1}".format(self.currentRoom.name, self.currentRoom.vnum))
			elif len(nameVnums) == 1:
				self.currentRoom = self.rooms[nameVnums[0]]
				self.isSynced = True
				self.clientSend(
					"Name-only synced to room {0} with vnum {1}".format(
						self.currentRoom.name,
						self.currentRoom.vnum
					)
				)
			else:
				self.clientSend("More than one room in the database matches current room. Unable to sync.")
		return self.isSynced

	def roomDetails(self):
		doors = []
		deathTraps = []
		oneWays = []
		undefineds = []
		for direction, exitObj in self.currentRoom.exits.items():
			if exitObj.door and exitObj.door != "exit":
				doors.append("{}: {}".format(direction, exitObj.door))
			if not exitObj.to or exitObj.to == "undefined":
				undefineds.append(direction)
			elif exitObj.to == "death":
				deathTraps.append(direction)
			elif (
				REVERSE_DIRECTIONS[direction] not in self.rooms[exitObj.to].exits
				or self.rooms[exitObj.to].exits[REVERSE_DIRECTIONS[direction]].to != self.currentRoom.vnum
			):
				oneWays.append(direction)
		if doors:
			self.clientSend("Doors: {}".format(", ".join(doors)), showPrompt=False)
		if deathTraps:
			self.clientSend("Death Traps: {}".format(", ".join(deathTraps)), showPrompt=False)
		if oneWays:
			self.clientSend("One ways: {}".format(", ".join(oneWays)), showPrompt=False)
		if undefineds:
			self.clientSend("Undefineds: {}".format(", ".join(undefineds)), showPrompt=False)
		if self.currentRoom.note:
			self.clientSend("Note: {}".format(self.currentRoom.note), showPrompt=False)

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
			if self.currentRoom.terrain not in (terrain, "deathtrap"):
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
				output.append("Adding exit '{}' to current room.".format(direction))
				self.currentRoom.exits[direction] = self.getNewExit(direction)
				if self.autoLinking:
					vnums = [
						vnum for vnum, roomObj in self.rooms.items()
						if (
							self.coordinatesAddDirection(
								(self.currentRoom.x, self.currentRoom.y, self.currentRoom.z),
								direction
							) == (roomObj.x, roomObj.y, roomObj.z)
						)
					]
					if (
						len(vnums) == 1
						and REVERSE_DIRECTIONS[direction] in self.rooms[vnums[0]].exits
						and self.rooms[vnums[0]].exits[REVERSE_DIRECTIONS[direction]].to == "undefined"
					):
						output.append(self.rlink("add {} {}".format(vnums[0], direction)))
			roomExit = self.currentRoom.exits[direction]
			if door and "door" not in roomExit.exitFlags:
				output.append(self.exitflags("add door {}".format(direction)))
			if road and "road" not in roomExit.exitFlags:
				output.append(self.exitflags("add road {}".format(direction)))
			if climb and "climb" not in roomExit.exitFlags:
				output.append(self.exitflags("add climb {}".format(direction)))
			if exitsOutput:
				exitsOutput.insert(0, "Exit {}:".format(direction))
				output.extend(exitsOutput)
				del exitsOutput[:]
		if output:
			return self.clientSend("\n".join(output))

	def autoMergeRoom(self, movement, roomObj):
		output = []
		if (
			self.autoLinking
			and REVERSE_DIRECTIONS[movement] in roomObj.exits
			and roomObj.exits[REVERSE_DIRECTIONS[movement]].to == "undefined"
		):
			output.append(self.rlink("add {} {}".format(roomObj.vnum, movement)))
		else:
			output.append(self.rlink("add oneway {} {}".format(roomObj.vnum, movement)))
		output.append("Auto Merging '{}' with name '{}'.".format(roomObj.vnum, roomObj.name))
		return self.clientSend("\n".join(output))

	def addNewRoom(self, movement, name, description, dynamic):
		vnum = self.getNewVnum()
		newRoom = roomdata.objects.Room(vnum)
		newRoom.name = name
		newRoom.desc = description
		newRoom.dynamicDesc = dynamic
		newRoom.x, newRoom.y, newRoom.z = self.coordinatesAddDirection(
			(self.currentRoom.x, self.currentRoom.y, self.currentRoom.z),
			movement
		)
		self.rooms[vnum] = newRoom
		if movement not in self.currentRoom.exits:
			self.currentRoom.exits[movement] = self.getNewExit(movement)
		self.currentRoom.exits[movement].to = vnum
		self.clientSend("Adding room '{}' with vnum '{}'".format(newRoom.name, vnum))

	def mud_event_prompt(self, data):
		self.prompt = data
		if self.isSynced:
			if self.autoMapping and self.moved:
				self.updateRoomFlags(self.prompt)
		elif self.roomName:
			self.sync(self.roomName, self.description)
		if self.isSynced and self.dynamic is not None:
			self.roomDetails()
			if self.autoWalkDirections and self.moved and self.autoWalk:
				# The player is auto-walking. Send the next direction to Mume.
				self.walkNextDirection()
		self.addedNewRoomFrom = None
		self.scouting = False
		self.movement = None
		self.moved = None
		self.roomName = None
		self.description = None
		self.dynamic = None
		self.exits = None

	def mud_event_movement(self, data):
		self.movement = data
		self.scouting = False

	def mud_event_line(self, data):
		if data.startswith("You quietly scout "):
			self.scouting = True
			return
		elif data == "A huge clock is standing here.":
			self.serverSend("look at clock")

		elif data == (
			"Wet, cold and filled with mud you drop down into a dark "
			"and moist cave, while you notice the mud above you moving "
			"to close the hole you left in the cave ceiling."
		):
			self.sync(vnum="17189")
		elif data == (
			"The gravel below your feet loosens, shifting slightly.. "
			"Suddenly, you lose your balance and crash to the cave floor below."
		):
			self.sync(vnum="15324")
		elif not self.timeSynchronized:
			self.syncTime(data)
		if MOVEMENT_FORCED_REGEX.search(data) or MOVEMENT_PREVENTED_REGEX.search(data):
			self.stopRun()
		if self.isSynced and self.autoMapping:
			if data == "It's too difficult to ride here." and self.currentRoom.ridable != "notridable":
				self.clientSend(self.rridable("notridable"))
			elif data == "You are already riding." and self.currentRoom.ridable != "ridable":
				self.clientSend(self.rridable("ridable"))

	def syncTime(self, data):
		if self.timeEvent is None:
			if CLOCK_REGEX.match(data):
				hour, minutes, amPm = CLOCK_REGEX.match(data).groups()
				# parsedHour should be 0 - 23.
				self.parsedHour = int(hour) % 12 + (12 if amPm == "pm" else 0)
				self.parsedMinutes = int(minutes)
				if self.parsedHour == 23 and self.parsedMinutes == 59:
					Timer(1.0, self.serverSend, "look at clock").start()
				else:
					self.timeEvent = "clock"
					self.serverSend("time")
			elif DAWN_REGEX.match(data):
				self.timeEvent = "dawn"
				self.timeEventOffset = 0
				self.serverSend("time")
			elif DAY_REGEX.match(data):
				self.timeEvent = "dawn"
				self.timeEventOffset = 1
				self.serverSend("time")
			elif DUSK_REGEX.match(data):
				self.timeEvent = "dusk"
				self.timeEventOffset = 0
				self.serverSend("time")
			elif NIGHT_REGEX.match(data):
				self.timeEvent = "dusk"
				self.timeEventOffset = 1
				self.serverSend("time")
		elif TIME_REGEX.match(data):
			match = TIME_REGEX.match(data)
			day = int(match.group("day"))
			year = int(match.group("year"))
			month = 0
			for i, m in enumerate(MONTHS):
				if m["westron"] == match.group("month") or m["sindarin"] == match.group("month"):
					month = i
					break
			if self.timeEvent == "dawn" or self.timeEvent == "dusk":
				self.parsedHour = MONTHS[month][self.timeEvent] + self.timeEventOffset
				self.parsedMinutes = 0
			self.clock.epoch = timeToEpoch(year, month, day, self.parsedHour, self.parsedMinutes)
			self.timeEvent = None
			self.timeEventOffset = 0
			self.timeSynchronized = True
			self.clientSend("Synchronized with epoch {}.".format(self.clock.epoch), showPrompt=False)

	def mud_event_name(self, data):
		if data not in ("You just see a dense fog around you...", "It is pitch black..."):
			self.roomName = simplified(data)
		else:
			self.roomName = ""

	def mud_event_description(self, data):
		self.description = simplified(data)

	def mud_event_dynamic(self, data):
		self.dynamic = data
		self.moved = None
		self.addedNewRoomFrom = None
		self.exits = None
		if not self.isSynced or self.movement is None:
			return
		elif not self.movement:
			# The player was forcibly moved in an unknown direction.
			self.isSynced = False
			self.clientSend("Forced movement, no longer synced.")
		elif self.movement not in DIRECTIONS:
			self.isSynced = False
			self.clientSend("Error: Invalid direction '{0}'. Map no longer synced!".format(self.movement))
		elif not self.autoMapping and self.movement not in self.currentRoom.exits:
			self.isSynced = False
			self.clientSend("Error: direction '{0}' not in database. Map no longer synced!".format(self.movement))
		elif not self.autoMapping and self.currentRoom.exits[self.movement].to not in self.rooms:
			self.isSynced = False
			self.clientSend(
				"Error: vnum ({}) in direction ({}) is not in the database. "
				"Map no longer synced!".format(
					self.currentRoom.exits[self.movement].to,
					self.movement
				)
			)
		else:
			if (
				self.autoMapping
				and self.movement in DIRECTIONS
				and (
					self.movement not in self.currentRoom.exits
					or self.currentRoom.exits[self.movement].to not in self.rooms
				)
			):
				# Player has moved in a direction that either doesn't exist in the database
				# or links to an invalid vnum (E.G. undefined).
				if self.autoMerging and self.roomName and self.description:
					duplicateRooms = self.searchRooms(exactMatch=True, name=self.roomName, desc=self.description)
				else:
					duplicateRooms = None
				if not self.roomName:
					self.clientSend("Unable to add new room: empty room name.")
				elif not self.description:
					self.clientSend("Unable to add new room: empty room description.")
				elif duplicateRooms and len(duplicateRooms) == 1:
					self.autoMergeRoom(self.movement, duplicateRooms[0])
				else:
					# Create new room.
					self.addedNewRoomFrom = self.currentRoom.vnum
					self.addNewRoom(self.movement, self.roomName, self.description, self.dynamic)
			self.currentRoom = self.rooms[self.currentRoom.exits[self.movement].to]
			self.moved = self.movement
			self.movement = None
			if self.autoMapping and self.autoUpdateRooms:
				if self.roomName and self.currentRoom.name != self.roomName:
					self.currentRoom.name = self.roomName
					self.clientSend("Updating room name.")
				if self.description and self.currentRoom.desc != self.description:
					self.currentRoom.desc = self.description
					self.clientSend("Updating room description.")
				if self.dynamic and self.currentRoom.dynamicDesc != self.dynamic:
					self.currentRoom.dynamicDesc = self.dynamic
					self.clientSend("Updating room dynamic description.")

	def mud_event_exits(self, data):
		exits = data
		if self.autoMapping and self.isSynced and self.moved:
			if self.addedNewRoomFrom and REVERSE_DIRECTIONS[self.moved] in exits:
				self.currentRoom.exits[REVERSE_DIRECTIONS[self.moved]] = self.getNewExit(
					direction=REVERSE_DIRECTIONS[self.moved],
					to=self.addedNewRoomFrom
				)
			self.updateExitFlags(exits)
		self.addedNewRoomFrom = None

	def handleUserData(self, data):
		if self.isEmulatingOffline:
			self.user_command_emu(decodeBytes(data).strip())
		else:
			userCommand = data.strip().split()[0]
			args = data[len(userCommand):].strip()
			getattr(self, "user_command_{}".format(decodeBytes(userCommand)))(decodeBytes(args))

	def handleMudEvent(self, event, data):
		data = stripAnsi(unescapeXML(decodeBytes(data)))
		if event in self.mudEventHandlers:
			if not self.scouting or event in ("prompt", "movement"):
				for handler in self.mudEventHandlers[event]:
					handler(data)
		elif event not in self.unknownMudEvents:
			self.unknownMudEvents.append(event)
			logger.debug("received data with an unknown event type of " + event)

	def registerMudEventHandler(self, event, handler):
		"""Registers a method to handle mud events of a given type.
		Params: event, handler
		where event is the name of the event type, typically corresponding to the XML tag of the incoming data,
		and handler is a method that takes a single argument, data, which is the text received from the mud.
		"""
		if event not in self.mudEventHandlers:
			self.mudEventHandlers[event] = set()
		self.mudEventHandlers[event].add(handler)

	def deregisterMudEventHandler(self, event, handler):
		"""Deregisters mud event handlers.
		params: same as registerMudEventHandler.
		"""
		if event in self.mudEventHandlers and handler in self.mudEventHandlers[event]:
			self.mudEventHandlers[event].remove(handler)

	def run(self):
		while True:
			try:
				dataType, data = self.queue.get()
				if data is None:
					break
				elif dataType == USER_DATA:
					# The data was a valid mapper command, sent from the user's mud client.
					self.handleUserData(data)
				elif dataType == MUD_DATA:
					# The data was from the mud server.
					event, data = data
					self.handleMudEvent(event, data)
			except Exception as e:
				self.output("map error")
				print("error " + str(e))
		self.clientSend("Exiting mapper thread.")
