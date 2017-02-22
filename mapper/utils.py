# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function

import os.path
import subprocess
import sys
from telnetlib import IAC, DONT, DO, WONT, WILL, theNULL, SB, SE, GA
import textwrap

from . import terminalsize


def simplified(text):
	result = []
	for character in text:
		if result and character in ("\t", "\n", "\v", "\f", "\r", " "):
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

def page(lines):
	"""Output word wrapped lines using the 'more' shell command if necessary."""
	lines = "\n".join(lines).splitlines()
	width, height = terminalsize.get_terminal_size()
	# Word wrapping to 1 less than the terminal width is necessary to prevent occasional blank lines in the terminal output.
	text = "\n".join(textwrap.fill(line.strip(), width - 1) for line in lines)
	if text.count("\n") +1 < height:
		print(text)
	else:
		more = subprocess.Popen("more", stdin=subprocess.PIPE, shell=True)
		more.stdin.write(text.encode("utf-8"))
		more.stdin.close()
		more.wait()
