# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import re

from ..gui.vec2d import Vec2d


COMPASS_DIRECTIONS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
AVOID_DYNAMIC_DESC_REGEX = re.compile(
	r"Some roots lie here waiting to ensnare weary travellers\.|"
	r"The remains of a clump of roots lie here in a heap of rotting compost\.|"
	r"A clump of roots is here, fighting|"
	r"Some withered twisted roots writhe towards you\.|"
	r"Black roots shift uneasily all around you\.|"
	r"black tangle of roots|"
	r"Massive roots shift uneasily all around you\.|"
	r"rattlesnake"
)
TERRAIN_COSTS = {
	"cavern": 0.75,
	"city": 0.75,
	"indoors": 0.75,
	"tunnel": 0.75,
	"road": 0.85,
	"field": 1.5,
	"brush": 1.8,
	"forest": 2.15,
	"hills": 2.45,
	"shallow": 2.45,
	"mountains": 2.8,
	"undefined": 30.0,
	"water": 50.0,
	"rapids": 60.0,
	"underwater": 100.0,
	"deathtrap": 1000.0
}
VALID_MOB_FLAGS = [
	"rent",
	"shop",
	"weapon_shop",
	"armour_shop",
	"food_shop",
	"pet_shop",
	"guild",
	"scout_guild",
	"mage_guild",
	"cleric_guild",
	"warrior_guild",
	"ranger_guild",
	"aggressive_mob",
	"quest_mob",
	"passive_mob",
	"elite_mob",
	"super_mob"
]
VALID_LOAD_FLAGS = [
	"treasure",
	"armour",
	"weapon",
	"water",
	"food",
	"herb",
	"key",
	"mule",
	"horse",
	"pack_horse",
	"trained_horse",
	"rohirrim",
	"warg",
	"boat",
	"attention",
	"tower",  # Player can 'watch' surrounding rooms from this one.
	"clock",
	"mail",
	"stable",
	"white_word",
	"dark_word",
	"equipment",
	"coach",
	"ferry"
]
VALID_EXIT_FLAGS = [
	"exit",
	"door",
	"road",
	"climb",
	"random",
	"special",
	"avoid",
	"no_match",
	"flow",
	"no_flee",
	"damage",
	"fall",
	"guarded"
]
VALID_DOOR_FLAGS = [
	"hidden",
	"need_key",
	"no_block",
	"no_break",
	"no_pick",
	"delayed",
	"callable",
	"knockable",
	"magic",
	"action",  # Action controlled
	"no_bash"
]


class Room(object):
	def __init__(self, vnum):
		self.vnum = vnum
		self.name = ""
		self.desc = ""
		self.dynamicDesc = ""
		self.note = ""
		self.terrain = "undefined"
		self.cost = TERRAIN_COSTS["undefined"]
		self.light = "undefined"
		self.align = "undefined"
		self.portable = "undefined"
		self.ridable = "undefined"
		self.avoid = False
		self.mobFlags = set()
		self.loadFlags = set()
		self.x = 0
		self.y = 0
		self.z = 0
		self.exits = {}

	def __lt__(self, other):
		# Unlike in Python 2 where most objects are sortable by default, our
		# Room class isn't automatically sortable in Python 3.
		# If we don't override this method, the path finder will throw an
		# exception in Python 3 because heapq.heappush requires that any object
		# passed to it be sortable.
		# We'll return False because we want heapq.heappush to sort the tuples
		# of movement cost and room object by the first item in the tuple (room cost),
		# and the order of rooms with the same movement cost is irrelevant.
		return False

	def calculateCost(self):
		try:
			self.cost = TERRAIN_COSTS[self.terrain]
		except KeyError:
			self.cost = TERRAIN_COSTS["undefined"]
		if self.avoid or AVOID_DYNAMIC_DESC_REGEX.search(self.dynamicDesc):
			self.cost += 1000.0
		if self.ridable == "notridable":
			self.cost += 5.0

	def manhattanDistance(self, destination):
		return abs(destination.x - self.x) + abs(destination.y - self.y) + abs(destination.z - self.z)

	def clockPositionTo(self, destination):
		# https://en.wikipedia.org/wiki/Clock_position
		delta = Vec2d(destination.x, destination.y) - (self.x, self.y)
		if self.vnum == destination.vnum:
			return "here"
		elif delta.get_length_sqrd() == 0:
			return "same X-Y"
		else:
			return "{:d} o'clock".format(round((90 - delta.get_angle_degrees() + 360) % 360 / 30) or 12)

	def directionTo(self, destination):
		delta = Vec2d(destination.x, destination.y) - (self.x, self.y)
		if self.vnum == destination.vnum:
			return "here"
		elif delta.get_length_sqrd() == 0:
			return "same X-Y"
		else:
			return COMPASS_DIRECTIONS[round((90 - delta.get_angle_degrees() + 360) % 360 / 45) % 8]


class Exit(object):
	def __init__(self):
		self.direction = None
		self.vnum = None
		self.to = "undefined"
		self.exitFlags = set(["exit"])
		self.door = ""
		self.doorFlags = set()
