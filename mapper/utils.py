# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os.path
import sys
from telnetlib import IAC, DONT, DO, WONT, WILL, theNULL, SB, SE, GA

WHITE_SPACE_CHARACTERS = frozenset(["\t", "\n", "\v", "\f", "\r", " "])


def simplified(text):
	whitespace = WHITE_SPACE_CHARACTERS
	result = []
	for character in text:
		if result and character in whitespace:
			if result[-1] != " ":
				result.append(" ")
		else:
			result.append(character)
	return "".join(result).strip()

def regexFuzzy(data):
	if not data:
		return ""
	elif isinstance(data, str):
		return "(".join(list(data)) + ")?" * (len(data) - 1)
	elif isinstance(data, list):
		return "|".join("(".join(list(item)) + ")?" * (len(item) - 1) for item in data)

def getDirectoryPath(directory):
	# This is needed for py2exe
	try:
		if sys.frozen or sys.importers:
			return os.path.join(os.path.dirname(sys.executable), directory)
	except AttributeError:
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", directory)

def iterItems(dictionary, **kw):
	try:
		return iter(dictionary.iteritems(**kw))
	except AttributeError:
		return iter(dictionary.items(**kw))

def multiReplace(text, replacements):
	try:
		replacements = iterItems(replacements)
	except AttributeError:
		# replacements is a list of tuples.
		pass
	for pattern, substitution in replacements:
		text = text.replace(pattern, substitution)
	return text

def decodeBytes(data):
	try:
		return data.decode("utf-8")
	except UnicodeDecodeError:
		return data.decode("latin-1")
	except AttributeError:
		return ""
