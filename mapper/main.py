# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function

import socket
from telnetlib import IAC, GA, DONT, DO, WONT, WILL, theNULL, SB, SE, TTYPE, NAWS
import threading

from .config import Config, config_lock
from .constants import USER_COMMANDS_REGEX, XML_UNESCAPE_PATTERNS
from .mapper import USER_DATA, MUD_DATA, Mapper
from .mpi import MPI
from .utils import multiReplace


class Proxy(threading.Thread):
	def __init__(self, client, server, mapper):
		threading.Thread.__init__(self)
		self.name = "Proxy"
		self._client = client
		self._server = server
		self._mapper = mapper
		self.alive = threading.Event()

	def close(self):
		self.alive.clear()

	def run(self):
		self.alive.set()
		while self.alive.isSet():
			try:
				data = self._client.recv(4096)
			except socket.timeout:
				continue
			except EnvironmentError:
				self.close()
				continue
			if not data:
				self.close()
			elif USER_COMMANDS_REGEX.match(data):
				self._mapper.queue.put((USER_DATA, data))
			else:
				try:
					self._server.sendall(data)
				except EnvironmentError:
					self.close()
					continue


class Server(threading.Thread):
	def __init__(self, client, server, mapper, outputFormat, use_gui):
		threading.Thread.__init__(self)
		self.name = "Server"
		self._client = client
		self._server = server
		self._mapper = mapper
		self._outputFormat = outputFormat
		self._use_gui = use_gui
		self.alive = threading.Event()

	def close(self):
		self.alive.clear()

	def run(self):
		self.alive.set()
		normalFormat = self._outputFormat == "normal"
		tinTinFormat = self._outputFormat == "tintin"
		rawFormat = self._outputFormat == "raw"
		ignoreBytes = frozenset([ord(theNULL), 0x11])
		negotiationBytes = frozenset(ord(byte) for byte in [DONT, DO, WONT, WILL])
		ordIAC = ord(IAC)
		ordGA = ord(GA)
		ordSB = ord(SB)
		ordSE = ord(SE)
		ordLF = ord("\n")
		inIAC = False
		inSubOption = False
		inMPI = False
		mpiThreads = []
		mpiCounter = 0
		mpiCommand = None
		mpiLen = None
		mpiBuffer = bytearray()
		clientBuffer = bytearray()
		tagBuffer = bytearray()
		textBuffer = bytearray()
		readingTag = False
		modeNone = 0
		modeRoom = 2
		modeName = 4
		modeDescription = 8
		modeExits = 16
		modePrompt = 32
		modeTerrain = 64
		xmlMode = modeNone
		tagReplacements = {
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
		initialOutput = b"".join((IAC, DO, TTYPE, IAC, DO, NAWS))
		encounteredInitialOutput = False
		while self.alive.isSet():
			try:
				data = self._server.recv(4096)
				if not data:
					self.close()
					continue
				elif not encounteredInitialOutput and data.startswith(initialOutput):
					# The connection to Mume has been established, and the game has just responded with the login screen.
					# Identify for Mume Remote Editing.
					self._server.sendall(b"~$#EI\n")
					# Turn on XML mode.
					self._server.sendall(b"~$#EX1\n3\n")
					# Tell the Mume server to put IAC-GA at end of prompts.
					self._server.sendall(b"~$#EP2\nG\n")
					encounteredInitialOutput = True
			except EnvironmentError:
				self.close()
				continue
			for byte in bytearray(data):
				if inIAC:
					clientBuffer.append(byte)
					if byte in negotiationBytes:
						# This is the second byte in a 3-byte telnet option sequence.
						# Skip the byte, and move on to the next.
						continue
					# From this point on, byte is the final byte in a 2-3 byte telnet option sequence.
					inIAC = False
					if byte == ordSB:
						# Sub-option negotiation begin
						inSubOption = True
					elif byte == ordSE:
						# Sub-option negotiation end
						inSubOption = False
					elif inSubOption:
						# Ignore subsequent bytes until the sub option negotiation has ended.
						continue
					elif byte == ordIAC:
						# This is an escaped IAC byte to be added to the buffer.
						mpiCounter = 0
						if inMPI:
							mpiBuffer.append(byte)
							# IAC + IAC was appended to the client buffer earlier.
							# It must be removed as MPI data should not be sent to the mud client.
							del clientBuffer[-2:]
						else:
							textBuffer.append(byte)
					elif byte == ordGA:
						del clientBuffer[-2:]
						clientBuffer.extend(b"\r\n")
						self._mapper.queue.put((MUD_DATA, ("iac_ga", b"")))
				elif byte == ordIAC:
					clientBuffer.append(byte)
					inIAC = True
				elif inSubOption or byte in ignoreBytes:
					clientBuffer.append(byte)
				elif inMPI:
					if byte == ordLF and mpiCommand is None and mpiLen is None:
						# The first line of MPI data was recieved.
						# The first byte is the MPI command, E for edit, V for view.
						# The remaining byte sequence is the length of the MPI data to be received.
						if mpiBuffer[0:1] in (b"E", b"V") and mpiBuffer[1:].isdigit():
							mpiCommand = mpiBuffer[0:1]
							mpiLen = int(mpiBuffer[1:])
						else:
							# Invalid MPI command or length.
							inMPI = False
						del mpiBuffer[:]
					else:
						mpiBuffer.append(byte)
						if mpiLen is not None and len(mpiBuffer) >= mpiLen:
							# The last byte in the MPI data has been reached.
							mpiThreads.append(MPI(client=self._client, server=self._server, isTinTin=tinTinFormat, command=mpiCommand, data=bytes(mpiBuffer)))
							mpiThreads[-1].start()
							del mpiBuffer[:]
							mpiCommand = None
							mpiLen = None
							inMPI = False
				elif byte == 126 and mpiCounter == 0 and clientBuffer.endswith(b"\n") or byte == 36 and mpiCounter == 1 or byte == 35 and mpiCounter == 2:
					# Byte is one of the first 3 bytes in the 4-byte MPI sequence (~$#E).
					mpiCounter += 1
				elif byte == 69 and mpiCounter == 3:
					# Byte is the final byte in the 4-byte MPI sequence (~$#E).
					inMPI = True
					mpiCounter = 0
				elif readingTag:
					mpiCounter = 0
					if byte == 62: # >
						# End of XML tag reached.
						if xmlMode == modeNone:
							if textBuffer:
								self._mapper.queue.put((MUD_DATA, ("misc", bytes(textBuffer))))
								del textBuffer[:]
							if tagBuffer.startswith(b"/xml"):
								pass
							elif tagBuffer.startswith(b"prompt"):
								xmlMode = modePrompt
							elif tagBuffer.startswith(b"exits"):
								xmlMode = modeExits
							elif tagBuffer.startswith(b"room"):
								xmlMode = modeRoom
							elif tagBuffer.startswith(b"movement"):
								self._mapper.queue.put((MUD_DATA, ("movement", bytes(tagBuffer)[8:].replace(b" dir=", b"", 1).split(b"/", 1)[0])))
							elif tagBuffer.startswith(b"status"):
								xmlMode = modeNone
						elif xmlMode == modeRoom:
							if tagBuffer.startswith(b"name"):
								xmlMode = modeName
							elif tagBuffer.startswith(b"description"):
								xmlMode = modeDescription
							elif tagBuffer.startswith(b"terrain"):
								# Terrain tag only comes up in blindness or fog
								xmlMode = modeTerrain
							elif tagBuffer.startswith(b"/room"):
								self._mapper.queue.put((MUD_DATA, ("dynamic", bytes(textBuffer))))
								del textBuffer[:]
								xmlMode = modeNone
						elif xmlMode == modeName and tagBuffer.startswith(b"/name"):
							self._mapper.queue.put((MUD_DATA, ("name", bytes(textBuffer))))
							del textBuffer[:]
							xmlMode = modeRoom
						elif xmlMode == modeDescription and tagBuffer.startswith(b"/description"):
							self._mapper.queue.put((MUD_DATA, ("description", bytes(textBuffer))))
							del textBuffer[:]
							xmlMode = modeRoom
						elif xmlMode == modeTerrain and tagBuffer.startswith(b"/terrain"):
							xmlMode = modeRoom
						elif xmlMode == modeExits and tagBuffer.startswith(b"/exits"):
							self._mapper.queue.put((MUD_DATA, ("exits", bytes(textBuffer))))
							del textBuffer[:]
							xmlMode = modeNone
						elif xmlMode == modePrompt and tagBuffer.startswith(b"/prompt"):
							self._mapper.queue.put((MUD_DATA, ("prompt", bytes(textBuffer))))
							del textBuffer[:]
							xmlMode = modeNone
						if tinTinFormat:
							clientBuffer.extend(tagReplacements.get(bytes(tagBuffer), b""))
						del tagBuffer[:]
						readingTag = False
					else:
						tagBuffer.append(byte)
					if rawFormat:
						clientBuffer.append(byte)
				elif byte == 60: # <
					# Start of new XML tag.
					mpiCounter = 0
					readingTag = True
					if rawFormat:
						clientBuffer.append(byte)
				else:
					# Byte is not part of a Telnet negotiation, MPI negotiation, or XML tag name.
					mpiCounter = 0
					textBuffer.append(byte)
					clientBuffer.append(byte)
			data = bytes(clientBuffer)
			if not rawFormat:
				data = multiReplace(data, XML_UNESCAPE_PATTERNS).replace(b"\r", b"").replace(b"\n\n", b"\n")
			try:
				self._client.sendall(data)
			except EnvironmentError:
				self.close()
				continue
			del clientBuffer[:]
		if self._use_gui:
			# Shutdown the gui
			with self._mapper._gui_queue_lock:
				self._mapper._gui_queue.put(None)
		# Join the MPI threads (if any) before joining the Mapper thread.
		for mpiThread in mpiThreads:
			mpiThread.join()


def main(outputFormat="normal", use_gui=None):
	outputFormat = outputFormat.strip().lower()
	if use_gui is None:
		from . import use_gui
	if use_gui:
		try:
			import pyglet
		except ImportError:
			print("Unable to find pyglet. Disabling the GUI")
			use_gui = False
	proxySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	proxySocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	proxySocket.bind(("", 4000))
	proxySocket.listen(1)
	clientConnection, proxyAddress = proxySocket.accept()
	clientConnection.settimeout(1.0)
	serverConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serverConnection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
	try:
		serverConnection.connect(("193.134.218.99", 443))
	except TimeoutError:
		try:
			clientConnection.sendall(b"\r\nError: server connection timed out!\r\n")
			clientConnection.sendall(b"\r\n")
			clientConnection.shutdown(socket.SHUT_RDWR)
		except EnvironmentError:
			pass
		clientConnection.close()
		return
	mapperThread = Mapper(client=clientConnection, server=serverConnection, use_gui=use_gui)
	proxyThread = Proxy(client=clientConnection, server=serverConnection, mapper=mapperThread)
	serverThread = Server(client=clientConnection, server=serverConnection, mapper=mapperThread, outputFormat=outputFormat, use_gui=use_gui)
	serverThread.start()
	proxyThread.start()
	mapperThread.start()
	if use_gui:
		pyglet.app.run()
	serverThread.join()
	try:
		serverConnection.shutdown(socket.SHUT_RDWR)
	except EnvironmentError:
		pass
	mapperThread.queue.put((None, None))
	mapperThread.join()
	try:
		clientConnection.sendall(b"\r\n")
		proxyThread.close()
		clientConnection.shutdown(socket.SHUT_RDWR)
	except EnvironmentError:
		pass
	proxyThread.join()
	serverConnection.close()
	clientConnection.close()
