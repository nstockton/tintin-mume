# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import random
import re
import subprocess
import sys
from telnetlib import IAC
import tempfile
import threading

from .utils import decodeBytes


TMP_DIR = tempfile.gettempdir()

class MPI(threading.Thread):
	def __init__(self, client, server, isTinTin=None, mpiMatch=None):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self.isTinTin = bool(isTinTin)
		self.mpiMatch = mpiMatch
		if sys.platform == "win32":
			self.editor = "notepad"
			self.pager = "notepad"
		else:
			self.editor = os.getenv("TINTINEDITOR", "nano -w")
			self.pager = os.getenv("TINTINPAGER", "less")

	def run(self):
		if not self.mpiMatch:
			return
		command = decodeBytes(self.mpiMatch["command"])
		length = int(decodeBytes(self.mpiMatch["length"]))
		session = decodeBytes(self.mpiMatch["session"]) if self.mpiMatch["session"] else ""
		if session:
			length -= len(session) + 1
		description = decodeBytes(self.mpiMatch["description"]) if self.mpiMatch["description"] else ""
		if description:
			length -= len(description) + 1
		body = decodeBytes(self.mpiMatch["body"])[:length].replace("\r", "").replace("\n", "\r\n")
		if command == "V":
			fileName = os.path.join(TMP_DIR, "V%d.txt" % random.randint(1000, 9999))
			with open(fileName, "wb") as fileObj:
				fileObj.write(body.encode("utf-8"))
			if self.isTinTin:
				print("MPICOMMAND:{0} {1}:MPICOMMAND".format(self.pager, fileName))
			else:
				pagerProcess = subprocess.Popen(self.pager.split() + [fileName])
				pagerProcess.wait()
		elif command == "E":
			fileName = os.path.join(TMP_DIR, "%s.txt" % session)
			with open(fileName, "wb") as fileObj:
				fileObj.write(body.encode("utf-8"))
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
				response = b"\n".join((self.mpiMatch["session"].replace(b"M", b"E"), fileObj.read().replace("\r", "").replace(IAC, IAC + IAC)))
			self._server.sendall(b"".join((b"~$#EE", str(len(response)).encode("utf-8"), b"\n", response)))
