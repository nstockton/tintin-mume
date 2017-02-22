# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function

import os
import subprocess
import sys
from telnetlib import IAC
import tempfile
import threading

from .utils import decodeBytes

def removeFile(fileObj):
	if not fileObj.closed:
		fileObj.close()
	try:
		os.unlink(fileObj.name)
	except FileNotFoundError:
		pass


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
		if self.command not in ("V", "E") or self.data is None:
			return
		elif self.command == "V":
			with tempfile.NamedTemporaryFile(suffix=".txt", prefix="mume_viewing_", delete=False) as fileObj:
				fileObj.write(self.data.replace("\n", "\r\n").encode("utf-8"))
			if self.isTinTin:
				print("MPICOMMAND:{0} {1}:MPICOMMAND".format(self.pager, fileObj.name))
			else:
				pagerProcess = subprocess.Popen(self.pager.split() + [fileObj.name])
				pagerProcess.wait()
				removeFile(fileObj)
		elif self.command == "E":
			session, description, body = self.data[1:].split("\n", 2)
			with tempfile.NamedTemporaryFile(suffix=".txt", prefix="mume_editing_", delete=False) as fileObj:
				fileObj.write(body.replace("\n", "\r\n").encode("utf-8"))
			lastModified = os.path.getmtime(fileObj.name)
			if self.isTinTin:
				print("MPICOMMAND:{0} {1}:MPICOMMAND".format(self.editor, fileObj.name))
				try:
					raw_input("Continue:")
				except NameError:
					input("Continue:")
			else:
				editorProcess = subprocess.Popen(self.editor.split() + [fileObj.name])
				editorProcess.wait()
			if os.path.getmtime(fileObj.name) == lastModified:
				# The user closed the text editor without saving. Cancel the editing session.
				response = b"C" + session.encode("utf-8")
			else:
				with open(fileObj.name, "rb") as fileObj:
					response = b"E" + session.encode("utf-8") + b"\n" + fileObj.read()
			response = response.replace(b"\r", b"").replace(IAC, IAC + IAC).strip() + b"\n"
			self._server.sendall(b"".join((b"~$#EE", str(len(response)).encode("utf-8"), b"\n", response)))
			removeFile(fileObj)
