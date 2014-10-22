import re
import sys

try:
	import tintin
except ImportError:
	tintin = None

IS_PYTHON_2 = sys.version_info[0] == 2

IS_PYTHON_3 = sys.version_info[0] == 3

IS_TINTIN = tintin is not None

MAP_FILE = "maps/arda.json"

SAMPLE_MAP_FILE = "maps/arda.json.sample"

LABELS_FILE = "data/room_labels.json"

SAMPLE_LABELS_FILE = "data/room_labels.json.sample"

DIRECTIONS = ["north", "east", "south", "west", "up", "down"]

USER_COMMANDS_REGEX = re.compile(br"^(?P<command>rinfo|run|stop|savemap|sync|rlabel)(?:\s+(?P<arguments>.*))?")

IGNORE_TAGS_REGEX = re.compile(r"<[/]?(?:xml|terrain|tell|say|narrate|pray|emote|magic|weather|header|status|song|shout|yell|social|hit|damage|avoid_damage|miss|enemy|familiar|snoop.*?|highlight.*?)>")

TINTIN_IGNORE_TAGS_REGEX = re.compile(br"<movement(?: dir=(?:north|south|east|west|up|down))?/>|<[/]?(?:xml|terrain|magic|weather|room|exits|header|status|song|shout|yell|social|hit|damage|avoid_damage|miss|enemy|familiar|snoop.*?|highlight.*?)>")

TINTIN_SEPARATE_TAGS_REGEX = re.compile(br"<(?P<tag>prompt|name|tell|say|narrate|pray|emote)>(?P<text>.*?)</(?P=tag)>", re.DOTALL|re.MULTILINE)

ROOM_TAGS_REGEX = re.compile(r"(?P<movement><movement(?: dir=(?P<movementDir>north|south|east|west|up|down))?/>)?<room><name>(?P<name>.+?)</name>[\r\n]*(?:<description>(?P<description>.*?)</description>)?(?P<dynamic>.*?)</room>(?:<exits>(?P<exits>.+?)</exits>)?.*?<prompt>(?P<prompt>.*?)</prompt>", re.DOTALL|re.MULTILINE)

EXIT_TAGS_REGEX = re.compile(r"(?P<direction>{directions})".format(directions="|".join(DIRECTIONS)))

ANSI_COLOR_REGEX = re.compile(r"\x1b\[[0-9;]+[m]")

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
			r"A (?:pony|dales-pony|horse|warhorse|pack horse|trained horse|horse of the Rohirrim|brown donkey|mountain mule|hungry warg|brown wolf)(?: \(\w\))? is too exhausted\.",
			r"You\'d better be swimming if you want to dive underwater\.",
			r"You need to climb to go there\.",
			r"You cannot climb there\.",
			r"If you still want to try\, you must \'climb\' there\.",
			r".+ (?:prevents|keeps) you from going (?:north|south|east|west|up|down|upstairs|downstairs|past (?:him|her|it))\.",
			r"Nah\.\.\. You feel too relaxed to do that\.",
			r"Maybe you should get on your feet first\?"
		]
	)
)

MOVEMENT_FORCED_REGEX = re.compile("|".join([
			r"You can\'t seem to escape the (?P<ignore>roots)\!",
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
			r"Stepping on the lizard corpses\, you use some depressions in the wall for support\, push the muddy ceiling apart and climb out of the cave\."
		]
	)
)

AVOID_VNUMS = [
	"540",
	"651",
	"676",
	"677",
	"679",
	"684",
	"687",
	"688",
	"856",
	"2361",
	"7735",
	"7736",
	"7739",
	"7746",
	"7747",
	"7750",
	"7760",
	"7761",
	"11691",
	"16650",
	"16713",
	"17534",
	"17538",
	"20794",
	"95125",
	"96553",
	"97407"
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

TERRAIN_SYMBOLS = {
	":": "brush",
	"O": "cavern",
	"#": "city",
	"?": "death",
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
	"U": "underwater",
	"~": "water"
}
