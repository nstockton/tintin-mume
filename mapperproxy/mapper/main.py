# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import socket
from telnetlib import IAC, DONT, DO, WONT, WILL, theNULL, SB, SE, GA, TTYPE, NAWS
import threading

from .constants import USER_COMMANDS_REGEX, TINTIN_IGNORE_TAGS_REGEX, TINTIN_SEPARATE_TAGS_REGEX, NORMAL_IGNORE_TAGS_REGEX, XML_UNESCAPE_PATTERNS
from .mapper import USER_DATA, MUD_DATA, Mapper
from .mpi import MPI
from .utils import multiReplace


class Proxy(threading.Thread):
	def __init__(self, client, server, mapper):
		threading.Thread.__init__(self)
		self.daemon = True
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
			except IOError:
				self.close()
				continue
			if not data:
				self.close()
			elif USER_COMMANDS_REGEX.match(data):
				self._mapper.queue.put((USER_DATA, data))
			else:
				self._server.sendall(data)


class Server(threading.Thread):
	def __init__(self, client, server, mapper, outputFormat):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self._mapper = mapper
		self._outputFormat = outputFormat

	def upperMatch(self, match):
		tag = match.group("tag").upper()
		text = match.group("text")
		if text is None:
			text = b""
		else:
			text = text.replace(b"\r\n", b"\n").replace(b"\n", b" ").strip()
		if tag == b"PROMPT" or tag == b"ENEMY":
			lineEnd = b""
			if tag == b"PROMPT":
				text = text.replace(b"<enemy>", b"").replace(b"</enemy>", b"")
		else:
			lineEnd = b"\r\n"
		return b"".join((tag, b":", text, b":", tag, lineEnd))

	def run(self):
		normalFormat = self._outputFormat == "normal"
		tinTinFormat = self._outputFormat == "tintin"
		rawFormat = self._outputFormat == "raw"
		ignoreBytes = frozenset([ord(theNULL), 0x11])
		negotiationBytes = frozenset(ord(byte) for byte in [DONT, DO, WONT, WILL])
		ordIAC = ord(IAC)
		ordSB = ord(SB)
		ordSE = ord(SE)
		ordGA = ord(GA)
		inIAC = False
		inSubOption = False
		inMPI = False
		mpiThreads = []
		mpiCounter = 0
		mpiCommand = None
		mpiLen = None
		mpiBuffer = bytearray()
		clientBuffer = bytearray()
		mapperBuffer = bytearray()
		initialOutput = b"".join((IAC, DO, TTYPE, IAC, DO, NAWS))
		encounteredInitialOutput = False
		while True:
			data = self._server.recv(4096)
			if not data:
				break
			elif not encounteredInitialOutput and data.startswith(initialOutput):
				# Identify for Mume Remote Editing.
				self._server.sendall(b"~$#EI\n")
				# Turn on XML mode.
				self._server.sendall(b"~$#EX1\n3\n")
				# Tell the Mume server to put IAC-GA at end of prompts.
				self._server.sendall(b"~$#EP2\nG\n")
				encounteredInitialOutput = True
			for byte in bytearray(data):
				if not inIAC:
					if byte == ordIAC:
						clientBuffer.append(byte)
						inIAC = True
					elif inSubOption or byte in ignoreBytes:
						clientBuffer.append(byte)
					elif inMPI:
						if byte == 10 and mpiCommand is None and mpiLen is None:
							if mpiBuffer[0:1] in (b"E", b"V") and mpiBuffer[1:].isdigit():
								mpiCommand = mpiBuffer[0:1]
								mpiLen = int(mpiBuffer[1:])
							else:
								inMPI = False
							del mpiBuffer[:]
							continue
						mpiBuffer.append(byte)
						if mpiLen is not None and len(mpiBuffer) >= mpiLen:
							# start MPI thread
							mpiThreads.append(MPI(client=self._client, server=self._server, isTinTin=tinTinFormat, command=mpiCommand, data=bytes(mpiBuffer)))
							mpiThreads[-1].start()
							del mpiBuffer[:]
							mpiCommand = None
							mpiLen = None
							inMPI = False
					elif byte == 126 and mpiCounter == 0 and clientBuffer.endswith(b"\n") or byte == 36 and mpiCounter == 1 or byte == 35 and mpiCounter == 2:
						mpiCounter = mpiCounter + 1
					elif byte == 69 and mpiCounter == 3:
						mpiCounter = 0
						inMPI = True
					else:
						mpiCounter = 0
						clientBuffer.append(byte)
						mapperBuffer.append(byte)
				else:
					if byte in negotiationBytes:
						# This is the second byte in a 3-byte telnet option sequence.
						# Skip the byte, and move on to the next.
						clientBuffer.append(byte)
						continue
					# From this point on, byte is the final byte in a 2-3 byte telnet option sequence.
					inIAC = False
					if byte == ordSB:
						# Sub-option negotiation begin
						clientBuffer.append(byte)
						inSubOption = True
					elif byte == ordSE:
						# Sub-option negotiation end
						clientBuffer.append(byte)
						inSubOption = False
					elif inSubOption:
						# Ignore subsequent bytes until the sub option negotiation has ended.
						clientBuffer.append(byte)
						continue
					elif byte == ordIAC:
						# This is an escaped IAC byte to be added to the buffer.
						mpiCounter = 0
						if inMPI:
							mpiBuffer.append(byte)
							del clientBuffer[-1]
						else:
							clientBuffer.append(byte)
							mapperBuffer.append(byte)
					elif byte == ordGA:
						# Mume will send an IAC-GA sequence after every prompt.
						clientBuffer.append(byte)
						self._mapper.queue.put((MUD_DATA, bytes(mapperBuffer)))
						del mapperBuffer[:]
					else:
						clientBuffer.append(byte)
			data = bytes(clientBuffer)
			if tinTinFormat:
				data = TINTIN_IGNORE_TAGS_REGEX.sub(b"", data)
				data = TINTIN_SEPARATE_TAGS_REGEX.sub(self.upperMatch, data)
				data = multiReplace(data, XML_UNESCAPE_PATTERNS).replace(b"\r\n", b"\n").replace(b"\n\n", b"\n")
			elif normalFormat:
				data = NORMAL_IGNORE_TAGS_REGEX.sub(b"", data)
				data = multiReplace(data, XML_UNESCAPE_PATTERNS)
			self._client.sendall(data)
			del clientBuffer[:]
		# Join the MPI threads (if any) before joining the Mapper thread.
		for mpiThread in mpiThreads:
			mpiThread.join()


def main(outputFormat="normal"):
	outputFormat = outputFormat.strip().lower()
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
		clientConnection.sendall(b"\r\nError: server connection timed out!\r\n")
		try:
			clientConnection.sendall(b"\r\n")
			clientConnection.shutdown(socket.SHUT_RDWR)
		except:
			pass
		clientConnection.close()
		return
	mapperThread = Mapper(client=clientConnection, server=serverConnection, outputFormat=outputFormat)
	proxyThread = Proxy(client=clientConnection, server=serverConnection, mapper=mapperThread)
	serverThread = Server(client=clientConnection, server=serverConnection, mapper=mapperThread, outputFormat=outputFormat)
	serverThread.start()
	proxyThread.start()
	mapperThread.start()
	serverThread.join()
	try:
		serverConnection.shutdown(socket.SHUT_RDWR)
	except:
		pass
	mapperThread.queue.put((None, None))
	mapperThread.join()
	try:
		clientConnection.sendall(b"\r\n")
		proxyThread.close()
		clientConnection.shutdown(socket.SHUT_RDWR)
	except:
		pass
	proxyThread.join()
	serverConnection.close()
	clientConnection.close()
