# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from .constants import PROMPT_REGEX
from .utils import simplified, multiReplace

XML_NONE = 0
XML_ROOM = 2
XML_NAME = 4
XML_DESCRIPTION = 8
XML_EXITS = 16
XML_PROMPT = 32
XML_TERRAIN = 64
XML_UNESCAPE_PATTERNS = (
	("&lt;", "<"),
	("&gt;", ">"),
	("&quot;", "\""),
	("&#39;", "'"),
	("&apos;", "'"),
	("&amp;", "&")
)

class MumeXMLParser(object):
	def __init__(self):
		self._xmlMode = XML_NONE
		self.rooms = []
		self._ignore = None
		self._movement = None
		self.lastPrompt = ">"

	def parse(self, data):
		[roomDict.clear() for roomDict in self.rooms]
		del self.rooms[:]
		tempTag = []
		tempCharacters = []
		readingTag = False
		for char in data:
			if readingTag:
				if char == ">":
					if tempTag:
						self._element("".join(tempTag))
						del tempTag[:]
					readingTag = False
					continue
				tempTag.append(char)
			else:
				if char == "<":
					self._text("".join(tempCharacters))
					del tempCharacters[:]
					readingTag = True
					continue
				tempCharacters.append(char)
		if not readingTag:
			self._text("".join(tempCharacters))
			del tempCharacters[:]
		return self.rooms

	def _element(self, line):
		if self._xmlMode == XML_NONE:
			if line.startswith("/xml"):
				pass
			elif line.startswith("prompt"):
				self._xmlMode = XML_PROMPT
			elif line.startswith("exits"):
				self._xmlMode = XML_EXITS
			elif line.startswith("room"):
				self.rooms.append({"name": "", "description": "", "dynamic": "", "exits": "", "prompt": "", "ignore": False})
				if self._movement is not None:
					self.rooms[-1]["movement"] = self._movement
					self._movement = None
				self._xmlMode = XML_ROOM
			elif line.startswith("movement"):
				self._movement = line[8:].replace(" dir=", "", 1).split("/", 1)[0]
			elif line.startswith("status"):
				self._xmlMode = XML_NONE
		elif self._xmlMode == XML_ROOM:
			if line.startswith("name"):
				self._xmlMode = XML_NAME
			elif line.startswith("description"):
				self._xmlMode = XML_DESCRIPTION
			elif line.startswith("terrain"):
				# Terrain tag only comes up in blindness or fog
				self._xmlMode = XML_TERRAIN
			elif line.startswith("/room"):
				self._xmlMode = XML_NONE
		elif self._xmlMode == XML_NAME:
			if line.startswith("/name"):
				self._xmlMode = XML_ROOM
		elif self._xmlMode == XML_DESCRIPTION:
			if line.startswith("/description"):
				self._xmlMode = XML_ROOM
		elif self._xmlMode == XML_EXITS:
			if line.startswith("/exits"):
				self._xmlMode = XML_NONE
		elif self._xmlMode == XML_PROMPT:
			if line.startswith("/prompt"):
				self._xmlMode = XML_NONE
		elif self._xmlMode == XML_TERRAIN:
			if line.startswith("/terrain"):
				self._xmlMode = XML_ROOM

	def _text(self, data):
		data = self.unescape(data)
		if not data:
			return
		elif self._xmlMode == XML_NONE:
			if "You were not able to keep your concentration while moving." in data and "You stop scouting." in data:
				self._ignore = None
			elif "You quietly scout " in data or "You can't seem to escape the roots!" in data:
				self._ignore = True
			return
		elif not self.rooms:
			return
		roomDict = self.rooms[-1]
		if self._xmlMode == XML_ROOM:
			# dynamic description
			roomDict["dynamic"] = "%s%s\n" % (roomDict["dynamic"], data)
		elif self._xmlMode == XML_NAME:
			roomDict["name"] = data
		elif self._xmlMode == XML_DESCRIPTION:
			roomDict["description"] = "%s%s\n" % (roomDict["description"], data)
		elif self._xmlMode == XML_EXITS:
			roomDict["exits"] = data
		elif self._xmlMode == XML_PROMPT:
			roomDict["prompt"] = data
			self.lastPrompt = data
			match = PROMPT_REGEX.search(data)
			if match is not None:
				roomDict.update(match.groupdict())
			if self._ignore:
				roomDict["ignore"] = True
				self._ignore = None

	def unescape(self, data):
		return simplified(multiReplace(data, XML_UNESCAPE_PATTERNS))
