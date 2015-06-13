# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import codecs
import itertools
import json
import os.path
import re
import subprocess
import textwrap

from .mapperworld import World
from .mapperconstants import DIRECTIONS, RUN_DESTINATION_REGEX, TERRAIN_SYMBOLS
from .terminalsize import get_terminal_size
from .utils import iterItems, getDirectoryPath


class EmulatedWorld(World):
	"""The main emulated world class"""
	width, height = get_terminal_size()

	def __init__(self, **kwargs):
		print("Loading the world database.")
		World.__init__(self)
		print("Loaded {0} rooms.".format(len(self.rooms)))
		self.config = {}
		dataDirectory = getDirectoryPath("data")
		self.configFile = os.path.join(dataDirectory, "emulation_config.json")
		self.sampleConfigFile = os.path.join(dataDirectory, "emulation_config.json.sample")
		self.loadConfig()
		# Set the initial room to the room that the user was in when the program last terminated.
		lastVnum = self.config.get("last_vnum", "0")
		if lastVnum not in self.rooms:
			lastVnum = sorted(self.rooms)[0]
		self.move(lastVnum)

	def output(self, text):
		"""Use less to display text if the number of lines exceeds the terminal height or the print function if not."""
		# Word wrapping to 1 less than the terminal width is necessary to prevent occasional blank lines in the terminal output.
		lines = [textwrap.fill(line.strip(), self.width - 1) for line in text.splitlines() if line.strip()]
		text = "\n".join(lines)
		if len(lines) < self.height:
			print(text)
		else:
			less = subprocess.Popen("less", stdin=subprocess.PIPE)
			less.stdin.write(text.encode("utf-8"))
			less.stdin.close()
			less.wait()
		return None

	def look(self):
		"""The 'look' command"""
		self.output(self.currentRoom.name)
		# If brief mode is disabled, output the room description
		if not self.config.get("brief", True):
			self.output(" ".join(line.strip() for line in self.currentRoom.desc.splitlines() if line.strip()))
		self.output(self.currentRoom.dynamicDesc)
		#loop through the list of exits in the current room, and build the doors/exits lines.
		doorList = []
		exitList = []
		for direction, exitObj in self.sortExits(self.currentRoom.exits):
			# If there is a door in that direction
			if exitObj.door or "door" in exitObj.exitFlags:
				doorList.append("{0}: {1}".format(direction, exitObj.door if exitObj.door else "exit"))
				if "hidden" not in exitObj.doorFlags:
					# The door is not a secret exit.
					# Enclose the direction of the door in parentheses '()' for use in the exits line. In Mume, enclosing an exits line direction in parentheses denotes an opened door in that direction.
					direction = "({0})".format(direction)
				else:
					# The door is a secret exit.
					# Enclose the direction of the door in brackets '[]' for use in the exits line. In Mume, enclosing an exits line direction in brackets denotes a closed door in that direction.
					direction = "[{0}]".format(direction)
			# The next 2 symbols which might be added are just convenience symbols for denoting if the exit is to an undefined room or a known deathtrap. They don't actually exist in Mume.
			if exitObj.to == "death":
				direction = "!!{0}!!".format(direction)
			elif exitObj.to not in self.rooms or exitObj.to == "undefined":
				direction = "??{0}??".format(direction)
			elif self.rooms[exitObj.to].terrain == "road":
				# The '=' sign is used in Mume to denote that the room in that direction is a road.
				direction = "={0}=".format(direction)
			elif "road" in exitObj.exitFlags:
				# The '-' sign is used in Mume to denote that the room in that direction is a trail.
				direction = "-{0}-".format(direction)
			exitList.append(direction)
		# If any of the exits had a door in that direction, print the direction and name of the door before the exits line.
		if doorList:
			self.output("Doors:")
			self.output(",\n".join(doorList))
		if not exitList:
			exitList.append("None!")
		self.output("Exits: {0}".format(", ".join(exitList)))
		if self.currentRoom.note:
			self.output("Note: {0}".format(self.currentRoom.note))
		# If the user has enabled the showing of room vnums in the configuration, print the room vnum.
		if self.config.get("show_vnum", True):
			self.output("Vnum: {0}".format(self.currentRoom.vnum))

	def longExits(self):
		"""The exits command"""
		self.output("Exits:")
		if not self.currentRoom.exits:
			return self.output("None!")
		for direction, exitObj in self.sortExits(self.currentRoom.exits):
			exitLine = []
			exitLine.append("{0}:".format(direction.capitalize()))
			if exitObj.door or "door" in exitObj.exitFlags:
				exitLine.append("{0} ({1}),".format("visible" if "hidden" not in exitObj.doorFlags else "hidden", exitObj.door if exitObj.door else "exit"))
			if exitObj.to.isdigit() and exitObj.to in self.rooms:
				exitLine.append("{0}, {1}".format(self.rooms[exitObj.to].name, self.rooms[exitObj.to].terrain))
			elif exitObj.to == "death":
				exitLine.append("death")
			else:
				exitLine.append("undefined")
			self.output(" ".join(exitLine))

	def move(self, text):
		"""Move to a given vnum, label, or in a given direction"""
		if text in DIRECTIONS:
			if text not in self.currentRoom.exits:
				return self.output("Alas, you cannot go that way!")
			else:
				vnum = self.currentRoom.exits[text].to
		elif text in self.labels:
			vnum = self.labels[text]
		elif text.isdigit():
			vnum = text
		else:
			return self.output("Error: {0} isn't a direction, label, or vnum.".format(text))
		if vnum == "undefined":
			return self.output("Undefined room in that direction!")
		elif vnum == "death":
			return self.output("Deathtrap in that direction!")
		elif vnum not in self.rooms:
			return self.output("Error: no rooms in the database with vnum ({0}).".format(vnum))
		self.currentRoom = self.rooms[vnum]
		self.config["last_vnum"] = vnum
		self.look()

	def toggleSetting(self, setting):
		"""Toggle configuration settings True/False"""
		self.config[setting] = self.config.get(setting, True) == False
		return self.config[setting]

	def loadConfig(self):
		"""Load the configuration file"""
		def getConfig(fileName):
			if os.path.exists(fileName):
				if not os.path.isdir(fileName):
					try:
						with codecs.open(fileName, "rb", encoding="utf-8") as fileObj:
							return json.load(fileObj)
					except IOError as e:
						self.output("{0}: '{1}'".format(e.strerror, e.filename))
						return {}
					except ValueError as e:
						self.output("Corrupted configuration file: {0}".format(fileName))
						return {}
				else:
					self.output("Error: '{0}' is a directory, not a file.".format(fileName))
					return {}
			else:
				return {}
		self.config.update(getConfig(self.sampleConfigFile))
		self.config.update(getConfig(self.configFile))

	def saveConfig(self):
		"""Save the configuration to disk"""
		with codecs.open(self.configFile, "wb", "utf-8") as fileObj:
			json.dump(self.config, fileObj, sort_keys=True, indent=2, separators=(",", ": "))

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

	def parseInput(self, userInput):
		"""Parse the user input"""
		match = re.match(r"^(?P<command>\S+)(?:\s+(?P<arguments>.*))?", userInput)
		command = match.group("command")
		arguments = match.group("arguments")
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(command))
		if direction:
			self.move(direction)
		elif "look".startswith(command):
			self.look()
		elif "exits".startswith(command):
			self.longExits()
		elif command == "vnum":
			status = self.toggleSetting("show_vnum")
			self.output("Show room vnum {0}.".format("enabled" if status else "disabled"))
		elif command == "brief":
			status = self.toggleSetting("brief")
			self.output("Brief mode {0}.".format("enabled" if status else "disabled"))
		elif command == "terrain":
			status = self.toggleSetting("use_terrain_symbols")
			self.output("Terrain symbols in prompt {0}.".format("enabled" if status else "disabled"))
		elif command == "path":
			if not arguments:
				self.pathFind()
			else:
				match = RUN_DESTINATION_REGEX.match(arguments)
				destination = match.group("destination")
				flags = match.group("flags")
				if flags:
					flags = flags.split("|")
				else:
					flags = None
				result = self.pathFind(destination=destination, flags=flags)
				if result is not None:
					self.output(self.createSpeedWalk(result))
		elif command == "rlabel":
			result = self.rlabel(arguments)
			if result:
				self.output("\n".join(result))
		elif command == "rinfo":
			self.output("\n".join(self.rinfo(arguments)))
		elif command in ("rnote", "ralign", "rlight", "rportable", "rridable", "rterrain", "rx", "ry", "rz", "rmobflags", "rloadflags", "exitflags", "doorflags", "secret", "rlink"):
			self.output(getattr(self, command)(arguments))
		elif command == "savemap":
			self.saveRooms()
		elif command.isdigit() or command in self.labels:
			self.move(command)
		else:
			self.output("Arglebargle, glop-glyf!?!")


def main():
	print("Welcome to Mume Map Emulation!")
	wld = EmulatedWorld()
	while True:
		prompt = "> "
		# Indicate the current room's terrain in the prompt.
		if not wld.config.get("use_terrain_symbols"):
			prompt = wld.currentRoom.terrain + prompt
		else:
			for symbol, terrain in iterItems(TERRAIN_SYMBOLS):
				if terrain == wld.currentRoom.terrain:
					prompt = symbol + prompt
					break
		# For Python 2/3 compatibility:
		try:
			userInput = raw_input(prompt).strip().lower()
		except NameError:
			userInput = input(prompt).strip().lower()
		if not userInput:
			continue
		elif "quit".startswith(userInput):
			break
		else:
			wld.parseInput(userInput)
	# The user has typed 'q[uit]'. Save the config file and exit.
	wld.saveConfig()
	print("Good bye.")
