import codecs

from .tintin import TinTin

def review(channelName, searchString=""):
	try:
		with codecs.open("communication/{0}.txt".format(channelName), "rb", encoding="utf-8") as channelFile:
			channelLines = channelFile.readlines()
	except IOError as e:
		return TinTin.echo("{0}: '{1}'".format(e.strerror, e.filename), "mume")
	searchString = searchString.strip()
	if not channelLines:
		# The channel log file is empty.
		output = ["{0} log is empty!".format(channelName.capitalize())]
	elif searchString.isdigit() and int(searchString) >= 1:
		# The search string is a number, so output the last (N) lines.
		output = channelLines[-int(searchString):]
	elif not searchString.isdigit() and searchString != "":
		# Output lines that contain the search string.
		output = [line for line in channelLines if searchString in line.lower()]
	else:
		# The search string is empty, so output the last 20 lines.
		output = channelLines[-20:]
	if not output:
		# A search string was specified, but no lines matched it.
		output = ["Nothing found!"]
	for line in output[-100:]:
		TinTin.echo(line.strip(), "mume")
