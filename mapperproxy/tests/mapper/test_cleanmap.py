# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from unittest.mock import Mock

from mapper.cleanmap import DIRECTIONS, ExitsCleaner, exitRegexp
from mapper.mapper import Mapper
from mapper.roomdata.objects import Exit, Room


class test_exitRegexp(unittest.TestCase):
	def test_exitsCommandRegexp_matches_allExitsThatAreNeitherOpenNorBrokenDoors(self):
		for exit in [
			"[North]  - A closed 'stabledoor'",
			"South   - The Path over the Bruinen",
			"[North]  - A closed 'marblegate'",
			"East    - On a Graceful Bridge",
			"South   - On a Balcony over the Bruinen",
			"West    - Meandering Path along the Bruinen",
			"Up      - At the Last Pavilion",
			"  [North]   - A closed 'curtain'",
			"  [East]   - A closed 'curtainthing'",
			"  [South]   - A closed 'wizardofozcurtain'",
			" ~[West]~   - A closed 'bedroomcurtain'",
			" ~[Up]~   - A closed 'DooMDoor'",
			" ~[Down]~   - A closed 'azZeuZjoec'",
		]:
			m = exitRegexp.match(exit)
			self.assertTrue(m, exit + " does not match the exitRegexp.")
			dir = m.group("dir").lower()
			self.assertTrue(
				dir in DIRECTIONS,
				dir + " is not a valid direction."
			)

	def test_exitRegexp_doesNotMatch_exitsThatAreOpenOrBrokenDoors_or_autoexits(self):
		for exit in [
			"#South#  - (archedfence) The Summer Terrace",
			"  (West)  - (door) a room",
			"None",
			"Exits: down.",
			"Exits: north, east, south, west."
			"Exits: none."
		]:
			m = exitRegexp.match(exit)
			self.assertFalse(m, exit + " should not match the exitRegexp, but it does.")


class TestExitsCleaner(unittest.TestCase):
	def setUp(self):
		self.mapper = Mock(spec=Mapper)
		self.mapper.isSynced = True
		self.mapper.autoUpdateRooms = True
		self.exitsCleaner = ExitsCleaner(self.mapper)

	def createRoom(self, *exits):
		room = Room("0")
		for dir, isHidden in exits:
			if dir not in DIRECTIONS:
				raise ValueError("Invalid direction " + dir + ". Cannot create room.")
			room.exits[dir] = Exit()
			if isHidden:
				room.exits[dir].doorFlags.add("hidden")
		return room

	def test_handle_withZeroOrOneExits(self):
		for room, exit in [
			(self.createRoom(), "None\r\n"),
			(self.createRoom(("east", False)), "None\r\n"),
			(self.createRoom(("south", True)), "None\r\n"),
			(self.createRoom(), "  (West)   - The Grand Hallway\r\n"),
			(self.createRoom(("up", False)), "  #Up#   - Private Stair\r\n"),
			(self.createRoom(("down", True)), "  [east]   - A closed 'EastDoorWhereYouThoughtThereWasADownExit\r\n"),
			(self.createRoom(), "  [North]   - A closed 'Northdoor'\r\n"),
			(self.createRoom(("east", False)), "  {East}   - You see something strange.\r\n"),
			(self.createRoom(), "  /West\\   - Western Slope\r\n"),
			(self.createRoom(("up", False)), "  Up   - Private Stair\r\n"),
			(self.createRoom(("down", True)), "Exits: *=Down=*   - Public Courtyard\r\n"),
		]:
			self.mapper.currentRoom = room
			self.exitsCleaner.handle(exit)
			self.mapper.user_command_secret.assert_not_called()
			self.mapper.user_command_secret.reset_mock()

		for room, exit in [
			(self.createRoom(("south", True)), "  \\South/   - Southern Slope\r\n"),
			(self.createRoom(("down", True)), "  *=Down=*   - Public Courtyard\r\n"),
		]:
			self.mapper.currentRoom = room
			dir = exitRegexp.match(exit).group("dir").lower()
			self.exitsCleaner.handle(exit)
			self.mapper.user_command_secret.assert_called_once_with("remove " + dir)
			self.mapper.user_command_secret.reset_mock()
