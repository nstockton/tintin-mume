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

	def _parse(self, file_name):
		data_directory = getDirectoryPath("data")
		file_name = os.path.join(data_directory, file_name)
		if os.path.exists(file_name):
			if not os.path.isdir(file_name):
				try:
					with codecs.open(file_name, "rb", encoding="utf-8") as file_object:
						return json.load(file_object)
				except IOError as e:
					raise Error("{}: '{}'".format(e.strerror, e.filename))
				except ValueError:
					raise Error("Corrupted json file: {}".format(file_name))
			else:
				raise Error("'{}' is a directory, not a file.".format(file_name))
		else:
			return {}

	def reload(self):
		self._config.clear()
		self._config.update(self._parse("{}.json.sample".format(self._name)))
		self._config.update(self._parse("{}.json".format(self._name)))

	def save(self):
		data_directory = getDirectoryPath("data")
		file_name = os.path.join(data_directory, "{}.json".format(self._name))
		with codecs.open(file_name, "wb", encoding="utf-8") as file_object:
			json.dump(self._config, file_object, sort_keys=True, indent=2, separators=(",", ": "))

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

config_lock = threading.Lock()
