# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
from telnetlib import IAC, DO, WILL, SB, SE, CHARSET, GA
import unittest

# Local Modules:
from . import parseMudOutput
from mapper.protocols.telnet import SB_ACCEPTED, SB_REQUEST, TelnetHandler


class TestTelnetHandler(unittest.TestCase):
	def testTelnetParse(self):
		clientReceives = bytearray()
		mudReceives = bytearray()
		handler = TelnetHandler(processed=clientReceives, remoteSender=mudReceives, promptTerminator=IAC + GA)
		text = b"Hello World!"
		self.assertEqual(parseMudOutput(handler, text), text)
		# Test if telnet negotiations are being properly filtered out.
		self.assertEqual(parseMudOutput(handler, IAC + GA + text + IAC + IAC + IAC + GA), text + IAC)
		# Test if the negotiation will be sent to the user's client.
		self.assertEqual(clientReceives, bytearray(IAC + GA + IAC + GA))

	def testCharset(self):
		clientReceives = bytearray()
		mudReceives = bytearray()
		handler = TelnetHandler(processed=clientReceives, remoteSender=mudReceives, promptTerminator=IAC + GA)
		# Tell the mud we wish to negotiate the charset.
		handler.charset("us-ascii")
		# Test if the mud receives our request.
		self.assertEqual(mudReceives, bytearray(IAC + WILL + CHARSET))
		mudReceives.clear()
		# Mud responds: IAC + DO + CHARSET. Make sure that the user's client doesn't receive it.
		self.assertEqual(parseMudOutput(handler, IAC + DO + CHARSET), bytearray())
		# Test that the mud receives our desired charset.
		self.assertEqual(mudReceives, bytearray(IAC + SB + CHARSET + SB_REQUEST + b";" + b"US-ASCII" + IAC + SE))
		mudReceives.clear()
		# Test that the mud responds, letting us know that the charset was accepted and will be used.
		self.assertEqual(
			parseMudOutput(handler, IAC + SB + CHARSET + SB_ACCEPTED + b"US-ASCII" + IAC + SE),
			bytearray()
		)
		# Make sure the mud didn't receive anything else from us.
		self.assertEqual(mudReceives, bytearray())
		# make sure that no part of the charset negotiation was sent to the user's client.
		self.assertEqual(clientReceives, bytearray())
