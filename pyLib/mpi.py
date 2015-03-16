import os
try:
	from Queue import Queue
except ImportError:
	from queue import Queue
import random
import re
import socket
import subprocess
import tempfile
import threading

from .mapperconstants import TELNET_NEGOTIATION_REGEX


MPI_REGEX = re.compile(r"~\$#E(?P<command>[EV])(?P<length>\d+)\n((?P<session>M\d+)(?:\n))?(?P<description>.+?)\n(?P<body>.*)", re.DOTALL | re.MULTILINE)
TMP_DIR = tempfile.gettempdir()

class MPI(threading.Thread):
	def __init__(self, client, server, mpiQueue, isTinTin=None):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self.mpiQueue = mpiQueue
		self.isTinTin = bool(isTinTin)
		self.editor = os.getenv("TINTINEDITOR", "nano -w")
		self.pager = os.getenv("TINTINPAGER", "less")

	def parse(self, data):
		data = self.decode(TELNET_NEGOTIATION_REGEX.sub(b"", b"".join(data.lstrip().splitlines(True)[:-1]))).replace("\x00", "")
		match = MPI_REGEX.search(data)
		if match is None:
			return
		result = match.groupdict()
		if result["command"] == "V":
			fileName = os.path.join(TMP_DIR, "V{0}.txt".format(random.randint(1000, 9999)))
			with open(fileName, "wb") as fileObj:
				fileObj.write(result["body"].encode("utf-8"))
			if self.isTinTin:
				print("MPICOMMAND:{0} {1}:MPICOMMAND".format(self.pager, fileName))
			else:
				pagerProcess = subprocess.Popen(self.pager.split() + [fileName])
				pagerProcess.wait()
		elif result["command"] == "E":
			fileName = os.path.join(TMP_DIR, "{0}.txt".format(result["session"]))
			with open(fileName, "wb") as fileObj:
				fileObj.write(result["body"].encode("utf-8"))
			if self.isTinTin:
				print("MPICOMMAND:{0} {1}:MPICOMMAND".format(self.editor, fileName))
				try:
					raw_input("Continue:")
				except NameError:
					input("Continue:")
			else:
				editorProcess = subprocess.Popen(self.editor.split() + [fileName])
				editorProcess.wait()
			with open(fileName, "rb") as fileObj:
				response = "\n".join((result["session"].replace("M", "E"), fileObj.read().decode("utf-8")))
			self._server.sendall("~$#EE{0}\n{1}".format(len(response), response).encode("utf-8"))

	def decode(self, bytes):
		try:
			return bytes.decode("utf-8")
		except UnicodeDecodeError:
			return bytes.decode("latin-1")
		except AttributeError:
			return None

	def run(self):
		buffer = b""
		while True:
			bytes = self.mpiQueue.get()
			if bytes is None:
				break
			buffer += bytes
			if b"\xff\xf9" in buffer:
				output, buffer = buffer.rsplit(b"\xff\xf9", 1)
				self.parse(output)
		self._client.sendall(b"\r\n" + "Exiting MPI thread.".encode("utf-8") + b"\r\n")
