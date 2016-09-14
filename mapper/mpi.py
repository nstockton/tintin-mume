# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import random
import subprocess
import sys
from telnetlib import IAC
import tempfile
import threading

from .utils import decodeBytes


TMP_DIR = tempfile.gettempdir()

class MPI(threading.Thread):
	def __init__(self, client, server, isTinTin=None, command=None, data=None):
		threading.Thread.__init__(self)
		self.daemon = True
		self._client = client
		self._server = server
		self.isTinTin = bool(isTinTin)
		self.command = decodeBytes(command)
		self.data = decodeBytes(data)
		if sys.platform == "win32":
			self.editor = "notepad"
			self.pager = "notepad"
		else:
			self.editor = os.getenv("TINTINEDITOR", "nano -w")
			self.pager = os.getenv("TINTINPAGER", "less")

	def run(self):
		if self.command is None or self.data is None:
			return
		elif self.command == "V":
			fileName = os.path.join(TMP_DIR, "V%d.txt" % random.randint(1000, 9999))
			with open(fileName, "wb") as fileObj:
				fileObj.write(self.data.replace("\n", "\r\n").encode("utf-8"))
			if self.isTinTin:
				print("MPICOMMAND:{0} {1}:MPICOMMAND".format(self.pager, fileName))
			else:
				pagerProcess = subprocess.Popen(self.pager.split() + [fileName])
				pagerProcess.wait()
		elif self.command == "E":
			session, description, body = self.data.split("\n", 2)
			fileName = os.path.join(TMP_DIR, "M%d.txt" % random.randint(1000, 9999))
			with open(fileName, "wb") as fileObj:
				fileObj.write(body.replace("\n", "\r\n").encode("utf-8"))
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
				response = b"\n".join((session.replace("M", "E").encode("utf-8"), fileObj.read().strip().replace(b"\r", b"").replace(IAC, IAC + IAC)))
			self._server.sendall(b"".join((b"~$#EE", str(len(response)).encode("utf-8"), b"\n", response, b"\n")))
