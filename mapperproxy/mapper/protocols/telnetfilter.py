# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging
from telnetlib import IAC, DO, DONT, WILL, WONT, SB, SE
import threading

# Local Modules:
from .base import BaseProtocolHandler


logger = logging.getLogger(__name__)


class TelnetFilter(BaseProtocolHandler):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._textBuffer = bytearray()
		self._optionNegotiationOrds = frozenset(ord(byte) for byte in (DONT, DO, WONT, WILL))
		self._inCommand = threading.Event()
		self._inSubOption = threading.Event()

	def parse(self, dataBytes):
		for ordinal in dataBytes:
			if self._inCommand.isSet():
				self._processed.append(ordinal)
				if ordinal in SB:
					# Sub-option begin.
					self._inSubOption.set()
				elif not self._inSubOption.isSet() and ordinal not in self._optionNegotiationOrds or ordinal in SE:
					self._inCommand.clear()
					if ordinal in SE:
						# Sub-option end.
						self._inSubOption.clear()
					elif ordinal in IAC:
						# Escaped IAC.
						# IAC + IAC was erroneously added to the processed buffer. Remove it.
						del self._processed[-2:]
						self._textBuffer.append(ordinal)
			elif ordinal in IAC:
				# The byte is the first byte of a 2-byte command / 3-byte option.
				self._processed.append(ordinal)
				self._inCommand.set()
			else:
				# The byte is not part of a Telnet negotiation.
				self._textBuffer.append(ordinal)
		if b"\n" in self._textBuffer:
			text, self._textBuffer = self._textBuffer.rsplit(b"\n", 1)
			text.extend(b"\n")
		else:
			text = b""
		result = (bytes(self._processed), bytes(text))
		self._processed.clear()
		return result
