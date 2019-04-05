# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import codecs
import json
import os.path

from ..utils import getDirectoryPath


DATA_DIRECTORY = getDirectoryPath("data")
LABELS_FILE = "room_labels.json"
SAMPLE_LABELS_FILE = "room_labels.json.sample"
LABELS_FILE_PATH = os.path.join(DATA_DIRECTORY, LABELS_FILE)
SAMPLE_LABELS_FILE_PATH = os.path.join(DATA_DIRECTORY, SAMPLE_LABELS_FILE)
MAP_FILE = "arda.json"
SAMPLE_MAP_FILE = "arda.json.sample"
MAP_DIRECTORY = getDirectoryPath("maps")
MAP_FILE_PATH = os.path.join(MAP_DIRECTORY, MAP_FILE)
SAMPLE_MAP_FILE_PATH = os.path.join(MAP_DIRECTORY, SAMPLE_MAP_FILE)


def _load(filePath):
	if os.path.exists(filePath):
		if not os.path.isdir(filePath):
			try:
				with codecs.open(filePath, "rb", encoding="utf-8") as fileObj:
					return None, json.load(fileObj)
			except IOError as e:
				return "{}: '{}'".format(e.strerror, e.filename), None
			except ValueError:
				return "Corrupted database file: {}".format(filePath), None
		else:
			return "Error: '{}' is a directory, not a file.".format(filePath), None
	else:
		return "Error: '{0}' doesn't exist.".format(filePath), None

def loadLabels():
	errorMessages = []
	labels = {}
	errors, result = _load(SAMPLE_LABELS_FILE_PATH)
	if result is None:
		errorMessages.append(errors)
		labels = None
	else:
		labels.update(result)
	errors, result = _load(LABELS_FILE_PATH)
	if result is None:
		errorMessages.append(errors)
	elif labels is None:
		labels = result
	else:
		labels.update(result)
	if errorMessages:
		return "\n".join(errorMessages), labels
	else:
		return None, labels

def dumpLabels(labels):
	with codecs.open(LABELS_FILE_PATH, "wb", encoding="utf-8") as fileObj:
		json.dump(labels, fileObj, sort_keys=True, indent=2, separators=(",", ": "))

def loadRooms():
	errorMessages = []
	errors, result = _load(MAP_FILE_PATH)
	if result is None:
		errorMessages.append(errors)
	else:
		return None, result
	errors, result = _load(SAMPLE_MAP_FILE_PATH)
	if result is None:
		errorMessages.append(errors)
		errorMessages.append("Error: neither '{}' nor '{}' can be found.".format(MAP_FILE_PATH, SAMPLE_MAP_FILE_PATH))
		return "\n".join(errorMessages), None
	else:
		return None, result

def dumpRooms(rooms):
	with codecs.open(MAP_FILE_PATH, "wb", encoding="utf-8") as fileObj:
		fileObj.write(json.dumps(rooms, sort_keys=True, indent=2, separators=(",", ": ")))
