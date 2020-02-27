# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging
from telnetlib import IAC
import threading

# Local Modules:
from .base import BaseProtocolHandler
from ..utils import escapeIAC


logger = logging.getLogger(__name__)


class XMLHandler(BaseProtocolHandler):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._tagBuffer = bytearray()  # Used for start and end tag names.
		self._textBuffer = bytearray()  # Used for the text between start and end tags.
		self._lineBuffer = bytearray()  # Used for non-XML lines.
		self._inTag = threading.Event()
		self._inGratuitous = threading.Event()
		self._mode = None
		self._modes = {  # If a tag matches a key, self._mode will be changed to its value.
			b"room": b"room",
			b"exits": b"exits",
			b"prompt": b"prompt",
			b"name": b"name",
			b"description": b"description",
			b"terrain": b"terrain",
			b"/exits": None,
			b"/prompt": None,
			b"/room": None,
			b"/name": b"room",
			b"/description": b"room",
			b"/terrain": b"room"
		}
		self._tintinReplacements = {  # Used for reformatting tags for Tintin.
			b"prompt": b"PROMPT:",
			b"/prompt": b":PROMPT",
			b"name": b"NAME:",
			b"/name": b":NAME",
			b"tell": b"TELL:",
			b"/tell": b":TELL",
			b"narrate": b"NARRATE:",
			b"/narrate": b":NARRATE",
			b"pray": b"PRAY:",
			b"/pray": b":PRAY",
			b"say": b"SAY:",
			b"/say": b":SAY",
			b"emote": b"EMOTE:",
			b"/emote": b":EMOTE"
		}

	def _handleTag(self, ordinal):
		modes = self._modes
		if ordinal in b">":
			# End of tag reached.
			self._inTag.clear()
			tag = bytes(self._tagBuffer)
			self._tagBuffer.clear()
			text = bytes(self._textBuffer)
			self._textBuffer.clear()
			if self._outputFormat == "raw":
				self._processed.extend(b"<" + escapeIAC(tag) + b">")
			elif self._outputFormat == "tintin" and not self._inGratuitous.isSet():
				self._processed.extend(self._tintinReplacements.get(escapeIAC(tag), b""))
			if self._mode is None and tag.startswith(b"movement"):
				self._sendEvent("movement", tag[13:-1])
			elif tag == b"gratuitous":
				self._inGratuitous.set()
			elif tag == b"/gratuitous":
				self._inGratuitous.clear()
			elif tag in modes:
				self._mode = modes[tag]
				if tag.startswith(b"/"):
					self._sendEvent("dynamic" if tag == b"/room" else tag[1:].decode("us-ascii"), text)
		else:
			self._tagBuffer.append(ordinal)

	def parse(self, ordinal):
		if self._inTag.isSet():
			self._handleTag(ordinal)
		elif ordinal in b"<":
			self._inTag.set()
		else:
			self._textBuffer.append(ordinal)
			if self._outputFormat == "raw" or not self._inGratuitous.isSet():
				self._processed.append(ordinal)
				if ordinal in IAC:
					self._processed.append(ordinal)  # Double the IAC to escape it.
			if self._mode is None:
				self._lineBuffer.append(ordinal)
				if ordinal in b"\n":
					line = bytes(self._lineBuffer.rstrip(b"\r\n"))
					self._lineBuffer.clear()
					self._sendEvent("line", line)
