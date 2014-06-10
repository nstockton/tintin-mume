import os.path
import json
from tintin import TinTin

DATABASE_FILE = "data/secret_exits.json"
SAMPLE_DATABASE_FILE = "data/secret_exits.json.sample"

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
	rooms = {}
else:
	try:
		with open(path, "rb") as data:
			rooms = json.load(data, encoding="UTF-8")
	except IOError as e:
		rooms = {}
		TinTin.echo("%s: '%s'" % (e.strerror, e.filename), "mume")
	except ValueError as e:
		rooms = {}
		TinTin.echo("Corrupted file: '%s'" % path, "mume")

validDirections = ["north", "south", "east", "west", "up", "down"]
roomName = ""

def uniq(lst):
	last = object()
	for item in lst:
		if item != last:
			yield item
			last = item

def save():
	with open(DATABASE_FILE, "wb") as data:
		json.dump(rooms, data, sort_keys=True, indent=2, separators=(",", ": "), encoding="UTF-8")

def setRoomName(name=""):
	global roomName
	roomName = name.strip().lower()

def info(text="", exactMatch=True):
	global rooms
	global roomName
	text = text.strip().lower()
	results = []
	if text:
		results.extend([name for name in rooms if text in name])
	elif roomName and roomName in rooms:
		text = roomName
		results.append(text)
	else:
		return TinTin.echo("Error!  Room undefined.", "mume")
	if not results:
		TinTin.echo("There aren't any rooms named '%s' in the database." % text, "mume")
	else:
		for result in sorted(results):
			exits = []
			for door, direction in rooms[result]:
				if direction:
					exits.append("%s (%s)" % (direction, door))
				else:
					exits.append("(%s)" % door)
			TinTin.echo("%s: %s" % (result, ", ".join(exits)), "mume")

def actionAll(action=""):
	global rooms
	global roomName
	currentRoom = roomName
	if not currentRoom:
		return TinTin.echo("Error!  Current room undefined.", "mume")
	elif currentRoom not in rooms:
		return TinTin.echo("There aren't any rooms named '%s' in the database." % currentRoom, "mume")
	elif not action:
		return TinTin.echo("Error! You must specify an action to perform.", "mume")
	for door, direction in rooms[currentRoom]:
		if direction:
			TinTin.send("%s %s %s" % (action, door, direction), "mume")
		else:
			TinTin.send("%s %s" % (action, door), "mume")

def add(newDoor="", newDirection=""):
	global rooms
	global roomName
	global validDirections
	currentRoom = roomName
	newDoor = newDoor.strip().lower()
	newDirection = newDirection.strip().lower()
	newDirection = "".join([dir for dir in validDirections if newDirection and dir.startswith(newDirection)])
	if not currentRoom:
		return TinTin.echo("Error!  Current room undefined.", "mume")
	elif not newDoor or not newDirection:
		return TinTin.echo("Syntax: dadd [door] [%s]" % "|".join(validDirections), "mume")
	elif currentRoom not in rooms:
		rooms[currentRoom] = []
	TinTin.echo("adding the door '%s' located '%s' to '%s'." % (newDoor, newDirection, currentRoom), "mume")
	rooms[currentRoom].append([newDoor, newDirection])
	rooms[currentRoom] = list(uniq(sorted(rooms[currentRoom], key=lambda (door, direction): validDirections.index(direction) if direction in validDirections else 0)))
	save()

def delete(delDoor="", delDirection=""):
	global rooms
	global roomName
	global validDirections
	currentRoom = roomName
	delDoor = delDoor.strip().lower()
	delDirection = delDirection.strip().lower()
	delDirection = "".join([dir for dir in validDirections+["all"] if delDirection and dir.startswith(delDirection)])
	if not currentRoom:
		return TinTin.echo("Error!  Room is undefined.", "mume")
	elif currentRoom not in rooms:
		return TinTin.echo("Error! The current room isn't in the database.", "mume")
	elif not delDoor or not delDirection:
		return TinTin.echo("Syntax: ddel [door|all] [%s|all]" % "|".join(validDirections), "mume")
	elif delDoor!="all" and delDirection!="all":
		if [delDoor, delDirection] in rooms[currentRoom]:
			TinTin.echo("Deleting '%s' located '%s' from '%s'." % (delDoor, delDirection, currentRoom), "mume")
			rooms[currentRoom].remove([delDoor, delDirection])
		else:
			return TinTin.echo("'%s' does not have any exits to the '%s' with the name '%s'." % (currentRoom, delDirection, delDoor), "mume")
	elif delDirection != "all":
		# Check to see if the current room has any secrets in the given direction.
		if [[door, direction] for door, direction in rooms[currentRoom] if direction == delDirection]:
			TinTin.echo("Deleting all exits '%s' from '%s'." % (delDirection, currentRoom), "mume")
			rooms[currentRoom] = [[door, direction] for door, direction in rooms[currentRoom] if direction != delDirection]
		else:
			return TinTin.echo("'%s' does not have any exits to the '%s'." % (currentRoom, delDirection), "mume")
	elif delDoor != "all":
		# Check to see if the current room has any secret doors with the given name.
		if [[door, direction] for door, direction in rooms[currentRoom] if door == delDoor]:
			TinTin.echo("Deleting all secret doors with the name '%s' from '%s'." % (delDoor, currentRoom), "mume")
			rooms[currentRoom] = [[door, direction] for door, direction in rooms[currentRoom] if door != delDoor]
		else:
			return TinTin.echo("'%s' does not have any secret doors called '%s'." % (currentRoom, delDoor), "mume")
	if delDoor=="all" and delDirection=="all" or not rooms[currentRoom]:
		TinTin.echo("Deleting the room '%s' from the database." % currentRoom, "mume")
		del rooms[currentRoom]
	save()
