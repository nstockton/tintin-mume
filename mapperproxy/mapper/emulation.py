# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import codecs
import json
import os.path
import re
import threading

from .world import DIRECTIONS, TERRAIN_SYMBOLS, World
from .clock import Clock
from .utils import page, getDirectoryPath


class EmulatedWorld(World):
	"""The main emulated world class"""
	def __init__(self, interface, findFormat):
		self.output("Welcome to Mume Map Emulation!")
		self.output("Loading the world database.")
		World.__init__(self, interface=interface)
		self.output("Loaded {0} rooms.".format(len(self.rooms)))
		self.findFormat = findFormat
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
		"""Output text with utils.page."""
		page(line for line in text.splitlines() if line.strip())

	def user_command_partial_look(self, *args):
		"""The 'look' command"""
		self.output(self.currentRoom.name)
		# If brief mode is disabled, output the room description
		if not self.config.get("brief", True):
			self.output(" ".join(line.strip() for line in self.currentRoom.desc.splitlines() if line.strip()))
		self.output(self.currentRoom.dynamicDesc)
		# Loop through the list of exits in the current room, and build the doors/exits lines.
		doorList = []
		exitList = []
		for direction, exitObj in self.sortExits(self.currentRoom.exits):
			# If there is a door in that direction
			if exitObj.door or "door" in exitObj.exitFlags:
				doorList.append("{0}: {1}".format(direction, exitObj.door if exitObj.door else "exit"))
				if "hidden" not in exitObj.doorFlags:
					# The door is not a secret exit.
					# Enclose the direction of the door in parentheses '()' for use in the exits line.
					# In Mume, enclosing an exits line direction in parentheses denotes an opened door in that direction.
					direction = "({0})".format(direction)
				else:
					# The door is a secret exit.
					# Enclose the direction of the door in brackets '[]' for use in the exits line.
					# In Mume, enclosing an exits line direction in brackets denotes a closed door in that direction.
					direction = "[{0}]".format(direction)
			# The next 2 symbols which might be added are just convenience
			# symbols for denoting if the exit is to an undefined room or a known deathtrap.
			# They don't actually exist in Mume.
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
		# If any of the exits had a door in that direction, print the direction
		# and name of the door before the exits line.
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

	def user_command_partial_exits(self, *args):
		"""The exits command"""
		self.output("Exits:")
		if not self.currentRoom.exits:
			return self.output("None!")
		for direction, exitObj in self.sortExits(self.currentRoom.exits):
			exitLine = []
			exitLine.append("{0}:".format(direction.capitalize()))
			if exitObj.door or "door" in exitObj.exitFlags:
				exitLine.append(
					"{hidden} ({door}),".format(
						hidden="visible" if "hidden" not in exitObj.doorFlags else "hidden",
						door=exitObj.door if exitObj.door else "exit"
					)
				)
			if exitObj.to.isdigit() and exitObj.to in self.rooms:
				exitLine.append("{0}, {1}".format(self.rooms[exitObj.to].name, self.rooms[exitObj.to].terrain))
			elif exitObj.to == "death":
				exitLine.append("death")
			else:
				exitLine.append("undefined")
			self.output(" ".join(exitLine))

	def user_command_clock(self, *args):
		"""The time command"""
		self.output(Clock().time())

	def user_command_brief(self, *args):
		status = self.toggleSetting("brief")
		self.output("Brief mode {}.".format("enabled" if status else "disabled"))

	def user_command_doorflags(self, *args):
		self.output(self.doorflags(*args))

	def user_command_exitflags(self, *args):
		self.output(self.exitflags(*args))

	def user_command_fdoor(self, *args):
		self.output(self.fdoor(self.findFormat, *args))

	def user_command_fdynamic(self, *args):
		self.output(self.fdynamic(self.findFormat, *args))

	def user_command_flabel(self, *args):
		self.output(self.flabel(self.findFormat, *args))

	def user_command_fname(self, *args):
		self.output(self.fname(self.findFormat, *args))

	def user_command_fnote(self, *args):
		self.output(self.fnote(self.findFormat, *args))

	def user_command_getlabel(self, *args):
		self.output(self.getlabel(*args))

	def user_command_path(self, *args):
		result = self.path(*args)
		if result is not None:
			self.output(result)

	def user_command_ralign(self, *args):
		self.output(self.ralign(*args))

	def user_command_ravoid(self, *args):
		self.output(self.ravoid(*args))

	def user_command_rdelete(self, *args):
		self.output(self.rdelete(*args))

	def user_command_rinfo(self, *args):
		self.output("\n".join(self.rinfo(*args)))

	def user_command_rlabel(self, *args):
		result = self.rlabel(*args)
		if result:
			self.output("\n".join(result))

	def user_command_rlight(self, *args):
		self.output(self.rlight(*args))

	def user_command_rlink(self, *args):
		self.output(self.rlink(*args))

	def user_command_rloadflags(self, *args):
		self.output(self.rloadflags(*args))

	def user_command_rmobflags(self, *args):
		self.output(self.rmobflags(*args))

	def user_command_rnote(self, *args):
		self.output(self.rnote(*args))

	def user_command_rportable(self, *args):
		self.output(self.rportable(*args))

	def user_command_rridable(self, *args):
		self.output(self.rridable(*args))

	def user_command_rterrain(self, *args):
		self.output(self.rterrain(*args))

	def user_command_rx(self, *args):
		self.output(self.rx(*args))

	def user_command_ry(self, *args):
		self.output(self.ry(*args))

	def user_command_rz(self, *args):
		self.output(self.rz(*args))

	def user_command_savemap(self, *args):
		self.saveRooms()

	def user_command_secret(self, *args):
		self.output(self.secret(*args))

	def user_command_terrain(self, *args):
		status = self.toggleSetting("use_terrain_symbols")
		self.output("Terrain symbols in prompt {}.".format("enabled" if status else "disabled"))

	def user_command_vnum(self, *args):
		status = self.toggleSetting("show_vnum")
		self.output("Show room vnum {}.".format("enabled" if status else "disabled"))

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
		self.user_command_partial_look()

	def toggleSetting(self, setting):
		"""Toggle configuration settings True/False"""
		self.config[setting] = not self.config.get(setting, True)
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
					except ValueError:
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

	def parseInput(self, userInput):
		"""Parse the user input"""
		userCommands = [
			func[len("user_command_"):] for func in dir(self)
			if not func.startswith("user_command_partial_") and func.startswith("user_command_")
		]
		userCommandsPartial = [
			func[len("user_command_partial_"):] for func in dir(self)
			if func.startswith("user_command_partial_")
		]
		match = re.match(r"^(?P<command>\S+)(?:\s+(?P<arguments>.*))?", userInput)
		command = match.group("command")
		arguments = match.group("arguments")
		direction = "".join(dir for dir in DIRECTIONS if dir.startswith(command))
		if direction:
			self.move(direction)
		elif [method for method in userCommandsPartial if method.startswith(command)]:
			completed = [method for method in userCommandsPartial if method.startswith(command)][0]
			getattr(self, "user_command_partial_{}".format(completed))(arguments)
		elif command in userCommands:
			getattr(self, "user_command_{}".format(command))(arguments)
		elif command.isdigit() or command in self.labels:
			self.move(command)
		else:
			self.output("Arglebargle, glop-glyf!?!")


class Emulator(threading.Thread):
	def __init__(self, interface, findFormat):
		threading.Thread.__init__(self)
		self.name = "Emulator"
		self.world = EmulatedWorld(interface, findFormat)
		self._interface = interface

	def run(self):
		wld = self.world
		while True:
			prompt = "> "
			# Indicate the current room's terrain in the prompt.
			if not wld.config.get("use_terrain_symbols"):
				prompt = wld.currentRoom.terrain + prompt
			else:
				for symbol, terrain in TERRAIN_SYMBOLS.items():
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
		wld.output("Good bye.")
		if self._interface != "text":
			with wld._gui_queue_lock:
				wld._gui_queue.put(None)


def main(interface, findFormat):
	interface = interface.strip().lower()
	if interface != "text":
		try:
			import pyglet
		except ImportError:
			print("Unable to find pyglet. Disabling gui")
			interface = "text"
	emulator_thread = Emulator(interface, findFormat)
	emulator_thread.start()
	if interface != "text":
		pyglet.app.run()
	emulator_thread.join()
