# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import sys

IS_PYTHON_2 = sys.version_info[0] == 2

MAP_FILE = "arda.json"

SAMPLE_MAP_FILE = "arda.json.sample"

LABELS_FILE = "room_labels.json"

SAMPLE_LABELS_FILE = "room_labels.json.sample"

DIRECTIONS = ["north", "east", "south", "west", "up", "down"]

RUN_DESTINATION_REGEX = re.compile(r"^(?P<destination>.+?)(?:\s+(?P<flags>\S+))?$")

PROMPT_REGEX = re.compile(r"^(?P<light>[@*!\)o]?)(?P<terrain>[\#\(\[\+\.%fO~UW:=<]?)(?P<weather>[*'\"~=-]{0,2})\s*(?P<movementFlags>[RrSsCcW]{0,4})[^\>]*\>$")

EXIT_TAGS_REGEX = re.compile(r"(?P<door>[\(\[\#]?)(?P<road>[=-]?)(?P<climb>[/\\]?)(?P<portal>[\{]?)(?P<direction>%s)" % "|".join(DIRECTIONS))

ANSI_COLOR_REGEX = re.compile(r"\x1b\[[\d;]+m")

AVOID_DYNAMIC_DESC_REGEX = re.compile(r"Some roots lie here waiting to ensnare weary travellers\.|The remains of a clump of roots lie here in a heap of rotting compost\.|A clump of roots is here, fighting|Some withered twisted roots writhe towards you\.|Black roots shift uneasily all around you\.|black tangle of roots|Massive roots shift uneasily all around you\.|rattlesnake")

MOVEMENT_PREVENTED_REGEX = re.compile("^%s$" % "|".join([
			r"The \w+ seem[s]? to be closed\.",
			r"It seems to be locked\.",
			r"You cannot ride there\.",
			r"Your boat cannot enter this place\.",
			r"A guard steps in front of you\.",
			r"The clerk bars your way\.",
			r"You cannot go that way\.\.\.",
			r"Alas\, you cannot go that way\.\.\.",
			r"You need to swim to go there\.",
			r"You failed swimming there\.",
			r"You failed to climb there and fall down\, hurting yourself\.",
			r"Your mount cannot climb the tree\!",
			r"No way\! You are fighting for your life\!",
			r"In your dreams\, or what\?",
			r"You are too exhausted\.",
			r"You unsuccessfully try to break through the ice\.",
			r"Your mount refuses to follow your orders\!",
			r"You are too exhausted to ride\.",
			r"You can\'t go into deep water\!",
			r"You don\'t control your mount\!",
			r"Your mount is too sensible to attempt such a feat\.",
			r"Oops\! You cannot go there riding\!",
			r"A (?:pony|dales-pony|horse|warhorse|pack horse|trained horse|horse of the Rohirrim|brown donkey|mountain mule|hungry warg|brown wolf)(?: \(\w+\))? (?:is too exhausted|doesn't want you riding (?:him|her|it) anymore)\.",
			r"You\'d better be swimming if you want to dive underwater\.",
			r"You need to climb to go there\.",
			r"You cannot climb there\.",
			r"If you still want to try\, you must \'climb\' there\.",
			r".+ (?:prevents|keeps) you from going (?:north|south|east|west|up|down|upstairs|downstairs|past (?:him|her|it))\.",
			r"Nah\.\.\. You feel too relaxed to do that\.",
			r"Maybe you should get on your feet first\?",
			r"Not from your present position\!"
		]
	)
)

MOVEMENT_FORCED_REGEX = re.compile("|".join([
			r"You feel confused and move along randomly\.\.\.",
			r"Suddenly an explosion of ancient rhymes makes the space collapse around you\!",
			r"The pain stops\, your vision clears\, and you realize that you are elsewhere\.",
			r"A guard leads you out of the house\.",
			r"You leave the ferry\.",
			r"You reached the riverbank\.",
			r"You stop moving towards the (?:left|right) bank and drift downstream\.",
			r"You are borne along by a strong current\.",
			r"You are swept away by the current\.",
			r"You are swept away by the powerful current of water\.",
			r"You board the ferry\.",
			r"You are dead\! Sorry\.\.\.",
			r"With a jerk\, the basket starts gliding down the rope towards the platform\.",
			r"#You cannot control your mount on the slanted and unstable surface\! You begin to slide to the north\, and plunge toward the water below\!",
			r"The current pulls you faster\. Suddenly\, you are sucked downwards into darkness\!",
			r"You are washed blindly over the rocks\, and plummet sickeningly downwards\.\.\.",
			r"Oops\! You walk off the bridge and fall into the rushing water below\!",
			r"Holding your breath and with closed eyes\, you are squeezed below the surface of the water\.",
			r"You tighten your grip as (:a Great Eagle|Gwaihir the Windlord) starts to descend fast\.",
			r"The trees confuse you\, making you wander around in circles\.",
			r"Sarion helps you outside\.",
			r"Stepping on the lizard corpses\, you use some depressions in the wall for support\, push the muddy ceiling apart and climb out of the cave\."
		]
	)
)

LEAD_BEFORE_ENTERING_VNUMS = [
	"196",
	"3473",
	"3474",
	"12138",
	"12637"
]

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
	"shallowwater": 2.45,
	"mountains": 2.8,
	"random": 30.0,
	"undefined": 30.0,
	"water": 50.0,
	"rapids": 60.0,
	"underwater": 100.0,
	"death": 1000.0
}

TERRAIN_COLORS = {
	"cavern": (153, 50, 204, 255),
	"city": (190, 190, 190, 255),
	"indoors": (186, 85, 211, 255),
	"tunnel": (153, 50, 204, 255),
	"road": (255, 255, 255, 255),
	"field": (124, 252, 0, 255),
	"brush": (127, 255, 0, 255),
	"forest": (8, 128, 0, 255),
	"hills": (139, 69, 19 ,255),
	"shallowwater": (218, 120, 245, 255),
	"mountains": (165, 42, 42, 255),
	"water": (32, 64, 192, 255),
	"rapids": (32, 64, 192, 255),
	"underwater": (48, 8, 120, 255),
	"unknown": (24, 16, 32, 255)
}

TERRAIN_SYMBOLS = {
	":": "brush",
	"O": "cavern",
	"#": "city",
	"!": "death",
	".": "field",
	"f": "forest",
	"(": "hills",
	"[": "indoors",
	"<": "mountains",
	"|": "random",
	"W": "rapids",
	"+": "road",
	"%": "shallowwater",
	"=": "tunnel",
	"?": "undefined",
	"U": "underwater",
	"~": "water"
}

LIGHT_SYMBOLS = {
	"@": "lit",
	"*": "lit",
	"!": "undefined",
	")": "lit",
	"o": "dark"
}

VALID_MOB_FLAGS = [
	"rent",
	"shop",
	"weaponshop",
	"armourshop",
	"foodshop",
	"petshop",
	"guild",
	"scoutguild",
	"mageguild",
	"clericguild",
	"warriorguild",
	"rangerguild",
	"smob",
	"quest",
	"any",
	"reserved2"
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
	"packhorse",
	"trainedhorse",
	"rohirrim",
	"warg",
	"boat",
	"attention",
	"tower",
	"clock",
	"mail",
	"stable"
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
	"needkey",
	"noblock",
	"nobreak",
	"nopick",
	"delayed",
	"callable",
	"knockable",
	"magic",
	"action"
]

DIRECTION_COORDINATES = {
	"north": (0, 1, 0),
	"south": (0, -1, 0),
	"west": (-1, 0, 0),
	"east": (1, 0, 0),
	"up": (0, 0, 1),
	"down": (0, 0, -1)
}

REVERSE_DIRECTIONS = {
	"north": "south",
	"south": "north",
	"east": "west",
	"west": "east",
	"up": "down",
	"down": "up"
}

XML_UNESCAPE_PATTERNS = (
	(b"&lt;", b"<"),
	(b"&gt;", b">"),
	(b"&quot;", b"\""),
	(b"&#39;", b"'"),
	(b"&apos;", b"'"),
	(b"&amp;", b"&")
)
