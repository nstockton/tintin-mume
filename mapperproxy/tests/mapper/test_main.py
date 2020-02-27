# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import socket
from queue import Empty, Queue
from telnetlib import CHARSET, GA, IAC, DO, NAWS, SB, SE, TTYPE, WILL
import unittest
from unittest.mock import call, Mock

# Local Modules:
from mapper.main import Server
from mapper.mapper import MUD_DATA
from mapper.protocols.mpi import MPI_INIT
from mapper.protocols.telnet import SB_ACCEPTED, SB_SEND


# The initial output of MUME. Used by the server thread to detect connection success.
INITIAL_OUTPUT = IAC + DO + TTYPE + IAC + DO + NAWS
WELCOME_MESSAGE = b"\r\n                              ***  MUME VIII  ***\r\n\r\n"


class TestServerThread(unittest.TestCase):
	def testServerThread(self):
		initialConfiguration = [  # What the server thread sends MUME on connection success.
			# Identify for Mume Remote Editing.
			MPI_INIT + b"I\n",
			# Turn on XML mode.
			MPI_INIT + b"X2\n3G\n",
			# Tell the Mume server to put IAC-GA at end of prompts.
			MPI_INIT + b"P2\nG\n"
		]
		mumeSocket = Mock(spec=socket.socket)
		outputFromMume = Queue()
		inputToMume = Queue()
		mumeSocket.recv.side_effect = lambda arg: outputFromMume.get()
		mumeSocket.sendall.side_effect = lambda data: inputToMume.put(data)
		clientSocket = Mock(spec=socket.socket)
		outputToUser = Queue()
		clientSocket.sendall.side_effect = lambda data: outputToUser.put(data)
		serverThread = Server(
			client=clientSocket,
			server=mumeSocket,
			mapper=Mock(),
			outputFormat=None,
			interface="text",
			promptTerminator=None
		)
		serverThread.daemon = True  # otherwise if this does not terminate, it prevents unittest from terminating
		serverThread.start()
		# test when the server sends its initial negotiations, the server thread outputs its initial configuration
		self.assertEqual(initialConfiguration, serverThread.initialConfiguration)
		self.assertEqual(INITIAL_OUTPUT, serverThread.initialOutput)
		outputFromMume.put(INITIAL_OUTPUT)
		try:
			# Expect IAC + WILL + CHARSET, even though it's not in initialConfiguration.
			initialConfiguration.append(IAC + WILL + CHARSET)
			while initialConfiguration:
				data = inputToMume.get(timeout=1)
				self.assertIn(data, initialConfiguration, "Unknown initial configuration: {!r}".format(data))
				initialConfiguration.remove(data)
		except Empty:
			errorMessage = (
				"The server thread did not output the expected number of configuration parameters.",
				"The yet-to-be-seen configurations are: {!r}".format(initialConfiguration)
			)
			raise AssertionError("\n".join(errorMessage))
		# test nothing extra has been sent yet
		if not inputToMume.empty():
			remainingOutput = inputToMume.get()
			errorMessage = (
				"The server thread spat out at least one unexpected initial configuration.",
				"Remaining output: {!r}".format(remainingOutput)
			)
			raise AssertionError("\n".join(errorMessage))
		# test initial telnet negotiations were passed to the client
		try:
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, INITIAL_OUTPUT)
		except Empty:
			raise AssertionError("initial telnet negotiations were not passed to the client")
		# test regular text is passed through to the client
		try:
			outputFromMume.put(WELCOME_MESSAGE)
			data = outputToUser.get(timeout=1)
			self.assertEqual(WELCOME_MESSAGE, data)
		except Empty:
			raise AssertionError("The welcome message was not passed through to the client within 1 second.")
		# test further telnet negotiations are passed to the client with the exception of charset negotiations
		try:
			charsetNegotiation = IAC + DO + CHARSET + IAC + SB + TTYPE + SB_SEND + IAC + SE
			charsetSubnegotiation = IAC + SB + CHARSET + SB_ACCEPTED + b"US-ASCII" + IAC + SE
			outputFromMume.put(charsetNegotiation)
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, charsetNegotiation[3:])  # slicing off the charset negotiation
			outputFromMume.put(charsetSubnegotiation)
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, b"")
		except Empty:
			raise AssertionError("Further telnet negotiations were not passed to the client")
		# when mume outputs further text, test it is passed to the user
		try:
			usernamePrompt = b"By what name do you wish to be known? "
			outputFromMume.put(usernamePrompt)
			data = outputToUser.get(timeout=1)
			self.assertEqual(data, usernamePrompt)
		except Empty:
			raise AssertionError("Further text was not passed to the user")
		# when mume outputs an empty string, test server thread closes within a second
		outputFromMume.put(b"")
		serverThread.join(1)
		self.assertFalse(serverThread.is_alive())


class TestServerThreadThroughput(unittest.TestCase):
	def setUp(self):
		self.mapperThread = Mock()
		self.serverThread = Server(
			client=Mock(),
			server=Mock(),
			mapper=self.mapperThread,
			outputFormat="normal",
			interface="text",
			promptTerminator=b"\r\n",
		)

	def tearDown(self):
		del self.mapperThread
		del self.serverThread

	def runThroughput(self, threadInput, expectedOutput, expectedData, inputDescription):
		res = self.serverThread._handler.parse(threadInput)
		self.assertEqual(
			res,
			expectedOutput,
			f"When entering {inputDescription}, the expected output did not match {expectedOutput}"
		)
		actualData = self.mapperThread.queue.put.mock_calls
		i = 0
		while len(actualData) > i < len(expectedData):
			self.assertEqual(
				actualData[i],
				expectedData[i],
				f"When entering {inputDescription}, call #{i} to the mapper queue was not as expected"
			)
			i += 1
		if i < len(actualData):
			raise AssertionError("The mapper queue received the unexpected data: " + str(actualData[i]))
		if i < len(expectedData):
			raise AssertionError("The mapper queue did not receive the expected data: " + str(expectedData[i]))

	def testProcessingPrompt(self):
		self.runThroughput(
			threadInput=b"<prompt>\x1b[34mMana:Hot Move:Tired>\x1b[0m</prompt>" + IAC + GA,
			expectedOutput=b"\x1b[34mMana:Hot Move:Tired>\x1b[0m\r\n",
			expectedData=[
				call((MUD_DATA, ("prompt", b"\x1b[34mMana:Hot Move:Tired>\x1b[0m")))
			],
			inputDescription="prompt with mana burning and moves tired"
		)

	def testProcessingEnteringRoom(self):
		threadInput = (
			b"<movement dir=down/><room><name>Seagull Inn</name>\r\n"
			+ b"<gratuitous><description>"
			+ b"This is the most famous meeting-place in Harlond where people of all sorts\r\n"
			+ b"exchange news, rumours, deals and friendships. Sailors from the entire coast of\r\n"
			+ b"Middle-earth, as far as Dol Amroth and even Pelargir, are frequent guests here.\r\n"
			+ b"For the sleepy, there is a reception and chambers upstairs. A note is stuck to\r\n"
			+ b"the wall.\r\n"
			+ b"</description></gratuitous>"
			+ b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here.\r\n"
			+ b"A white-painted bench is here.\r\n"
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here.\r\n"
			+ b"An elven lamplighter is resting here.\r\n"
			+ b"</room>"
		)
		expectedOutput = (
			b"Seagull Inn\r\n"
			+ b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here.\r\n"
			+ b"A white-painted bench is here.\r\n"
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here.\r\n"
			+ b"An elven lamplighter is resting here.\r\n"
		)
		expectedDesc = (
			b"This is the most famous meeting-place in Harlond where people of all sorts\r\n"
			+ b"exchange news, rumours, deals and friendships. Sailors from the entire coast of\r\n"
			+ b"Middle-earth, as far as Dol Amroth and even Pelargir, are frequent guests here.\r\n"
			+ b"For the sleepy, there is a reception and chambers upstairs. A note is stuck to\r\n"
			+ b"the wall.\r\n"
		)
		expectedDynamicDesc = (
			b"A large bulletin board, entitled \"Board of the Free Peoples\", is mounted here.\r\n"
			+ b"A white-painted bench is here.\r\n"
			+ b"Eldinor the owner and bartender of the Seagull Inn is serving drinks here.\r\n"
			+ b"An elven lamplighter is resting here.\r\n"
		)
		expectedData = [
			call((MUD_DATA, ("movement", b"down"))),
			call((MUD_DATA, ("name", b"Seagull Inn"))),
			call((MUD_DATA, ("description", expectedDesc))),
			call((MUD_DATA, ("dynamic", expectedDynamicDesc))),
		]
		inputDescription = "moving into a room"
		self.runThroughput(threadInput, expectedOutput, expectedData, inputDescription)
