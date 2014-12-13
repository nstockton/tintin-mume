import codecs
import json
import os.path

from .tintin import TinTin

DATABASE_FILE = "data/secret_exits.json"
SAMPLE_DATABASE_FILE = "data/secret_exits.json.sample"
VALID_DIRECTIONS = ["north", "south", "east", "west", "up", "down"]


class Secrets(object):
	def __init__(self):
		if os.path.exists(DATABASE_FILE):
			if not os.path.isdir(DATABASE_FILE):
				path = DATABASE_FILE
			else:
				TinTin.echo("Error: '{0}' is a directory, not a file.".format(DATABASE_FILE), "python")
		elif os.path.exists(SAMPLE_DATABASE_FILE):
			if not os.path.isdir(SAMPLE_DATABASE_FILE):
				path = SAMPLE_DATABASE_FILE
			else:
				TinTin.echo("Error: '{0}' is a directory, not a file.".format(SAMPLE_DATABASE_FILE), "python")
		else:
			path = None
			TinTin.echo("Error: neither '{0}' nor '{1}' can be found.".format(DATABASE_FILE, SAMPLE_DATABASE_FILE), "mume")
		if not path:
			self.rooms = {}
		else:
			try:
				with codecs.open(path, "rb", encoding="utf-8") as data:
					self.rooms = json.load(data)
			except IOError as e:
				self.rooms = {}
				TinTin.echo("{0}: '{1}'".format(e.strerror, e.filename), "mume")
			except ValueError as e:
				self.rooms = {}
				TinTin.echo("Corrupted file: '{0}'".format(path), "mume")

	def uniq(self, lst):
		last = object()
		for item in lst:
			if item != last:
				yield item
				last = item

	def save(self):
		with codecs.open(DATABASE_FILE, "wb", encoding="utf-8") as data:
			json.dump(self.rooms, data, sort_keys=True, indent=2, separators=(",", ": "))

	def info(self, roomName="", searchString=""):
		roomName = roomName.strip().lower()
		searchString = searchString.strip().lower()
		results = []
		if searchString:
			results.extend([name for name in self.rooms if searchString in name])
		elif roomName and roomName in self.rooms:
			searchString = roomName
			results.append(searchString)
		else:
			return TinTin.echo("Error!  Room undefined.", "mume")
		if not results:
			TinTin.echo("There aren't any rooms named '{0}' in the database.".format(searchString), "mume")
		else:
			for result in sorted(results):
				exits = []
				for door, direction in self.rooms[result]:
					if direction:
						exits.append("{0} ({1})".format(direction, door))
					else:
						exits.append("({0})".format(door))
				TinTin.echo("{0}: {1}".format(result, ", ".join(exits)), "mume")

	def actionAll(self, roomName="", action=""):
		roomName = roomName.strip().lower()
		if not roomName:
			return TinTin.echo("Error!  Current room undefined.", "mume")
		elif roomName not in self.rooms:
			return TinTin.echo("There aren't any rooms named '{0}' in the database.".format(roomName), "mume")
		elif not action:
			return TinTin.echo("Error! You must specify an action to perform.", "mume")
		for door, direction in self.rooms[roomName]:
			if direction:
				TinTin.send("{0} {1} {2}".format(action, door, direction), "mume")
			else:
				TinTin.send("{0} {1}".format(action, door), "mume")

	def add(self, roomName="", newDoor="", newDirection=""):
		roomName = roomName.strip().lower()
		newDoor = newDoor.strip().lower()
		newDirection = newDirection.strip().lower()
		# If the direction name is shortened, expand it to its full form.
		newDirection = "".join(dir for dir in VALID_DIRECTIONS if newDirection and dir.startswith(newDirection))
		if not roomName:
			return TinTin.echo("Error!  Current room undefined.", "mume")
		elif not newDoor or not newDirection:
			return TinTin.echo("Syntax: dadd [door] [{0}]".format("|".join(VALID_DIRECTIONS)), "mume")
		elif roomName not in self.rooms:
			self.rooms[roomName] = []
		TinTin.echo("adding the door '{0}' located '{1}' to '{2}'.".format(newDoor, newDirection, roomName), "mume")
		self.rooms[roomName].append([newDoor, newDirection])
		self.rooms[roomName] = list(self.uniq(sorted(self.rooms[roomName], key=lambda (door, direction): VALID_DIRECTIONS.index(direction) if direction in VALID_DIRECTIONS else 0)))
		self.save()

	def delete(self, roomName="", delDoor="", delDirection=""):
		roomName = roomName.strip().lower()
		delDoor = delDoor.strip().lower()
		delDirection = delDirection.strip().lower()
		# If the direction name is shortened, expand it to its full form.
		delDirection = "".join(dir for dir in VALID_DIRECTIONS + ["all"] if delDirection and dir.startswith(delDirection))
		if not roomName:
			return TinTin.echo("Error!  Room is undefined.", "mume")
		elif roomName not in self.rooms:
			return TinTin.echo("Error! The current room isn't in the database.", "mume")
		elif not delDoor or not delDirection:
			return TinTin.echo("Syntax: ddel [door|all] [{0}|all]".format("|".join(VALID_DIRECTIONS)), "mume")
		elif delDoor != "all" and delDirection != "all":
			if [delDoor, delDirection] in self.rooms[roomName]:
				TinTin.echo("Deleting '{0}' located '{1}' from '{2}'.".format(delDoor, delDirection, roomName), "mume")
				self.rooms[roomName].remove([delDoor, delDirection])
			else:
				return TinTin.echo("'{0}' does not have any exits to the '{1}' with the name '{2}'.".format(roomName, delDirection, delDoor), "mume")
		elif delDirection != "all":
			# Check to see if the current room has any secrets in the given direction.
			if [[door, direction] for door, direction in self.rooms[roomName] if direction == delDirection]:
				TinTin.echo("Deleting all exits '{0}' from '{1}'.".format(delDirection, roomName), "mume")
				self.rooms[roomName] = [[door, direction] for door, direction in self.rooms[roomName] if direction != delDirection]
			else:
				return TinTin.echo("'{0}' does not have any exits to the '{1}'.".format(roomName, delDirection), "mume")
		elif delDoor != "all":
			# Check to see if the current room has any secret doors with the given name.
			if [[door, direction] for door, direction in self.rooms[roomName] if door == delDoor]:
				TinTin.echo("Deleting all secret doors with the name '{0}' from '{1}'.".format(delDoor, roomName), "mume")
				self.rooms[roomName] = [[door, direction] for door, direction in self.rooms[roomName] if door != delDoor]
			else:
				return TinTin.echo("'{0}' does not have any secret doors called '{1}'.".format(roomName, delDoor), "mume")
		if delDoor == "all" and delDirection == "all" or not self.rooms[roomName]:
			TinTin.echo("Deleting the room '{0}' from the database.".format(roomName), "mume")
			del self.rooms[roomName]
		self.save()
