import os.path
import json
from tintin import TinTin

DATABASE_FILE = "data/room_labels.json"
SAMPLE_DATABASE_FILE = "data/room_labels.json.sample"

if os.path.exists(DATABASE_FILE):
	if not os.path.isdir(DATABASE_FILE):
		path = DATABASE_FILE
	else:
		TinTin.echo("Error: '%s' is a directory, not a file." % DATABASE_FILE, "python")
elif os.path.exists(SAMPLE_DATABASE_FILE):
	if not os.path.isdir(SAMPLE_DATABASE_FILE):
		path = SAMPLE_DATABASE_FILE
	else:
		TinTin.echo("Error: '%s' is a directory, not a file." % SAMPLE_DATABASE_FILE, "python")
else:
	path = None
	TinTin.echo("Error: neither '%s' nor '%s' can be found." % (DATABASE_FILE, SAMPLE_DATABASE_FILE), "mume")

if not path:
	labels = {}
else:
	try:
		with open(path, "rb") as data:
			labels = json.load(data, encoding="UTF-8")
	except IOError as e:
		labels = {}
		TinTin.echo("%s: '%s'" % (e.strerror, e.filename), "mume")
	except ValueError as e:
		labels = {}
		TinTin.echo("Corrupted file: '%s'" % path, "mume")

def save():
	with open(DATABASE_FILE, "wb") as data:
		json.dump(labels, data, sort_keys=True, indent=2, separators=(",", ": "), encoding="UTF-8")

def info(label=""):
	global labels
	label = label.strip().lower()
	if not label:
		TinTin.echo("Error! You must specify a label.", "mume")
	elif "all".startswith(label):
		if labels:
			for key, value in labels.iteritems():
				TinTin.echo("%s: %s" % (key, value), "mume")
		else:
			TinTin.echo("There aren't any labels in the database yet.", "mume")
	elif label not in labels:
		TinTin.echo("There aren't any labels matching '%s' in the database." % label, "mume")
	else:
		TinTin.echo("Label '%s' points to room '%s'." % (label, labels[label]), "mume")

def doLabel(label="", action=""):
	global labels
	label = label.strip().lower()
	if not label:
		return TinTin.echo("Error! You must specify a label.", "mume")
	elif label not in labels:
		return TinTin.echo("There aren't any labels matching '%s' in the database." % label, "mume")
	elif not action:
		return TinTin.echo("Error! You must specify an action to perform.", "mume")
	TinTin.execute("%s %s" % (action, labels[label]), "mume")

def add(label="", vnum=""):
	global labels
	label = label.strip().lower()
	vnum = vnum.strip().lower()
	if not label:
		return TinTin.echo("Error! You must specify a label.", "mume")
	elif not vnum:
		return TinTin.echo("Error! You must specify a VNum.", "mume")
	elif not vnum.isdigit():
		return TinTin.echo("Error! VNums must be numbers.", "mume")
	TinTin.echo("adding the label '%s' with VNum '%s'." % (label, vnum), "mume")
	labels[label] = vnum
	save()

def delete(label=""):
	global labels
	label = label.strip().lower()
	if not label:
		return TinTin.echo("Error! You must specify a label.", "mume")
	elif label not in labels:
		return TinTin.echo("There aren't any labels matching '%s' in the database." % label, "mume")
	TinTin.echo("Deleting label '%s'." % label, "mume")
	del labels[label]
	save()
