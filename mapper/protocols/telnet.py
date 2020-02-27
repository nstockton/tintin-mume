# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging
from telnetlib import IAC, DO, DONT, WILL, WONT, SB, SE, CHARSET, GA
import threading

# Local Modules:
from .base import BaseProtocolHandler
from ..utils import escapeIAC


# Some sub-option constants that aren't defined in the telnetlib module.
SB_IS, SB_SEND, SB_INFO = (bytes([i]) for i in range(3))
# The Q Method of Implementing TELNET Option Negotiation (RFC 1143).
NO, YES, EXPECT_NO, EXPECT_YES, EXPECT_NO_OPPOSITE, EXPECT_YES_OPPOSITE = (i for i in range(6))
REMOTE = 0
LOCAL = 1
# Telnet charset sub-option (RFC 2066).
SB_REQUEST, SB_ACCEPTED, SB_REJECTED, SB_TTABLE_IS, SB_TTABLE_REJECTED, SB_TTABLE_ACK, SB_TTABLE_NAK = (
	bytes([i]) for i in range(1, 8)
)


logger = logging.getLogger(__name__)


class TelnetHandler(BaseProtocolHandler):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._optionNegotiationOrds = frozenset(ord(byte) for byte in (DONT, DO, WONT, WILL))
		self._inCommand = threading.Event()
		self._optionNegotiation = None
		self._inSubOption = threading.Event()
		self._subOptionBuffer = bytearray()
		self.charsets = {
			"us-ascii": b"US-ASCII",
			"latin-1": b"ISO-8859-1",
			"utf-8": b"UTF-8"
		}
		self._options = {
			CHARSET: {
				"separator": b";",
				"name": self.charsets["us-ascii"]
			}
		}

	def _sendOption(self, command, option):
		self._sendRemote(IAC + command + option, raw=True)

	def _handleCommand(self, ordinal):
		if ordinal in IAC:
			# Escaped IAC, ignore.
			pass
		elif ordinal in SB:
			# Sub-option begin.
			self._inSubOption.set()
		elif ordinal in GA:
			# MUME will send IAC + GA after a prompt.
			self._processed.extend(self._promptTerminator if self._promptTerminator is not None else IAC + GA)
		elif ordinal in self._optionNegotiationOrds and self._optionNegotiation is None:
			self._optionNegotiation = ordinal
		else:
			self._processed.extend((IAC[0], ordinal))
		self._inCommand.clear()

	def _handleOption(self, ordinal):
		command = bytes([self._optionNegotiation])
		self._optionNegotiation = None
		option = bytes([ordinal])
		if option in self._options:
			if command == WILL or command == WONT:
				nvt = REMOTE
				rxAccept = WILL
				txAccept = DO
				txDeny = DONT
			else:
				nvt = LOCAL
				rxAccept = DO
				txAccept = WILL
				txDeny = WONT
			if nvt not in self._options[option]:
				self._options[option][nvt] = NO
			if command == rxAccept:
				if self._options[option][nvt] == NO:
					self._options[option][nvt] = YES
					self._sendOption(txAccept, option)
				elif self._options[option][nvt] == EXPECT_NO:
					self._options[option][nvt] = NO
				elif self._options[option][nvt] == EXPECT_NO_OPPOSITE:
					self._options[option][nvt] = YES
				elif self._options[option][nvt] == EXPECT_YES_OPPOSITE:
					self._options[option][nvt] = EXPECT_NO
					self._sendOption(txDeny, option)
				else:
					self._options[option][nvt] = YES
					if option == CHARSET:
						logger.debug("MUME acknowledges our request, tells us to begin charset negotiation.")
						# Negotiate the character set.
						separator = self._options[CHARSET]["separator"]
						name = self._options[CHARSET]["name"]
						logger.debug(f"Tell MUME we would like to use the '{name.decode('us-ascii')}' charset.")
						self.sendSubOption(CHARSET, SB_REQUEST + separator + name)
			else:
				if self._options[option][nvt] == YES:
					self._options[option][nvt] = NO
					self._sendOption(txDeny, option)
				elif self._options[option][nvt] == EXPECT_NO_OPPOSITE:
					self._options[option][nvt] = EXPECT_YES
					self._sendOption(txAccept, option)
				else:
					self._options[option][nvt] = NO
		else:
			self._processed.extend(IAC + command + option)

	def _handleSubOption(self, ordinal):
		if self._subOptionBuffer.endswith(IAC) and ordinal in SE:
			# Sub-option end.
			del self._subOptionBuffer[-1]  # Remove IAC from the end.
			option = bytes([self._subOptionBuffer.pop(0)])
			if option == CHARSET:
				status = self._subOptionBuffer[:1]
				response = self._subOptionBuffer[1:]
				name = self._options[CHARSET]["name"]
				if status == SB_ACCEPTED:
					logger.debug(f"MUME responds: Charset '{response.decode('us-ascii')}' accepted.")
				elif status == SB_REJECTED:
					# Note: MUME does not respond with the charset name if it was rejected.
					logger.warning(f"MUME responds: Charset '{name.decode('us-ascii')}' rejected.")
				else:
					logger.warning(
						"Unknown charset negotiation response from MUME: "
						+ repr(IAC + SB + CHARSET + self._subOptionBuffer + IAC + SE)
					)
			else:
				self._processed.extend(IAC + SB + option + self._subOptionBuffer + IAC + SE)
			self._subOptionBuffer.clear()
			self._inSubOption.clear()
		else:
			self._subOptionBuffer.append(ordinal)

	def sendCommand(self, command):
		self._sendRemote(IAC + command, raw=True)

	def sendSubOption(self, option, dataBytes):
		self._sendRemote(IAC + SB + option + escapeIAC(dataBytes) + IAC + SE, raw=True)

	def isOptionEnabled(self, option, nvt, state=YES):
		return (
			option in self._options
			and nvt in self._options[option]
			and self._options[option][nvt] == state
		)

	def enableOption(self, option, nvt):
		if nvt == REMOTE:
			txAccept = DO
		else:
			txAccept = WILL
		if option not in self._options:
			self._options[option] = {}
		if nvt not in self._options[option] or self._options[option][nvt] == NO:
			self._options[option][nvt] = EXPECT_YES
			self._sendOption(txAccept, option)
		elif self._options[option][nvt] == EXPECT_NO:
			self._options[option][nvt] = EXPECT_NO_OPPOSITE
		elif self._options[option][nvt] == EXPECT_YES_OPPOSITE:
			self._options[option][nvt] = EXPECT_YES

	def disableOption(self, option, nvt):
		if nvt == REMOTE:
			txDeny = DONT
		else:
			txDeny = WONT
		if option not in self._options:
			self._options[option] = {}
		if nvt not in self._options[option]:
			self._options[option][nvt] = NO
		elif self._options[option][nvt] == YES:
			self._options[option][nvt] = EXPECT_NO
			self._sendOption(txDeny, option)
		elif self._options[option][nvt] == EXPECT_YES:
			self._options[option][nvt] = EXPECT_YES_OPPOSITE
		elif self._options[option][nvt] == EXPECT_NO_OPPOSITE:
			self._options[option][nvt] = EXPECT_NO

	def charset(self, name):
		logger.debug("Ask MUME to negotiate charset.")
		# Tell the server that we will negotiate the character set.
		self._options[CHARSET]["name"] = self.charsets[name]
		self.enableOption(CHARSET, LOCAL)

	def parse(self, ordinal):
		if self._inSubOption.isSet():
			# The byte is part of a sub-negotiation.
			self._handleSubOption(ordinal)
		elif self._optionNegotiation is not None:
			# The byte is the final byte of a 3-byte option.
			self._handleOption(ordinal)
		elif self._inCommand.isSet():
			# The byte is the final byte of a 2-byte command, or the second byte of a 3-byte option.
			self._handleCommand(ordinal)
			if ordinal in IAC:
				# Escaped IAC.
				return ordinal
		elif ordinal in IAC:
			# The byte is the first byte of a 2-byte command / 3-byte option.
			self._inCommand.set()
		else:
			# The byte is not part of a Telnet negotiation.
			return ordinal
