import yaml
from tintin import TinTin

DATABASE_FILE = "data/room_labels.yml"

with open(DATABASE_FILE, "rb") as data:
	labels = yaml.safe_load(data)

def save():
	with open(DATABASE_FILE, "wb") as data:
		yaml.safe_dump(labels, data, default_flow_style=False, indent=4, line_break="\r\n")

def info(label=""):
	global labels
	label = label.strip().lower()
	if not label:
		return TinTin.echo("Error! You must specify a label.", "mume")
	elif label not in labels:
		return TinTin.echo("There aren't any labels matching '%s' in the database." % label, "mume")
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
