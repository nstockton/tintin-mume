# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from .mudevents import Handler
from .world import DIRECTIONS

directionsRegexp = "|".join([d.title() for d in DIRECTIONS])
exitRegexp = re.compile(
	r".*(?<![#(])(?P<dir>" + directionsRegexp + r")(?![#)]).* +- .*"
)


class ExitsCleaner(Handler):
	event = "exits"

	def handle(self, data):
		"""Receives the output from the exit command in Mume.
		Checks if the output indicates any exits that are definitely not hidden despite being flagged as so,
		then removes any such secret exit from the map.
		"""
		if not self.mapper.autoUpdateRooms or data.startswith("Exits:"):
			return
		for line in data.split("\r\n"):
			m = exitRegexp.match(line)
			if m:
				room = self.mapper.currentRoom
				dir = m.group("dir").lower()
				if self.mapper.isSynced and dir in room.exits and "hidden" in room.exits[dir].doorFlags:
					self.mapper.user_command_secret("remove " + dir)
