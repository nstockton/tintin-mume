# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import codecs
import collections
import json
import os.path
import threading

# Local Modules:
from .utils import getDirectoryPath


config_lock = threading.RLock()


class Error(Exception):
	pass


class Config(collections.MutableMapping):
	def __init__(self, name="config", *args, **kwargs):
		super(Config, self).__init__(*args, **kwargs)
		self._name = name
		self._config = dict()
		self.reload()

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		self._name = value

	def _parse(self, filename):
		data_directory = getDirectoryPath("data")
		filename = os.path.join(data_directory, filename)
		if os.path.exists(filename):
			if not os.path.isdir(filename):
				try:
					with codecs.open(filename, "rb", encoding="utf-8") as fileObj:
						return json.load(fileObj)
				except IOError as e:
					raise Error("{}: '{}'".format(e.strerror, e.filename))
				except ValueError:
					raise Error("Corrupted json file: {}".format(filename))
			else:
				raise Error("'{}' is a directory, not a file.".format(filename))
		else:
			return {}

	def reload(self):
		self._config.clear()
		self._config.update(self._parse("{}.json.sample".format(self._name)))
		self._config.update(self._parse("{}.json".format(self._name)))

	def save(self):
		data_directory = getDirectoryPath("data")
		filename = os.path.join(data_directory, "{}.json".format(self._name))
		with codecs.open(filename, "wb", encoding="utf-8") as fileObj:
			# Configuration should be stored using Windows style line endings (\r\n)
			# so the file can be viewed in Notepad.
			# However, codecs.open forces opening files in binary mode, which
			# prevents the use of the newline flag to force a particular delimiter for new lines.
			# The json data must therefore be modified to replace Unix line endings
			# with Windows line endings before it is written.
			data = json.dumps(self._config, sort_keys=True, indent=2)
			fileObj.write(data.replace("\n", "\r\n"))

	def __getitem__(self, key):
		return self._config[key]

	def __setitem__(self, key, value):
		self._config[key] = value

	def __delitem__(self, key):
		del self._config[key]

	def __iter__(self):
		return iter(self._config)

	def __len__(self):
		return len(self._config)
