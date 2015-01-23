# TinTin-MUME
A collection of TinTin++ scripts for [MUME](http://mume.org "MUME Home Page")

## Installation
These scripts require the latest beta version of TinTin. You can download the current TinTin Beta version from [here](http://tintin.sf.net/download/tintin-beta.tar.gz "TinTin Beta Version Direct Link").

## Usage
Here is a brief alias reference for the scripts, until more detailed information can be written.
### Communication
Rep - Sends a tell to the last person that told you something.
pl - Review prays.
nl - Review narrates.
sl - Review says.
tl - Review tells.
if a number is passed to one of the communication review aliases, the script will display that many lines of output (up to 100) from the bottom of the communication file. If a string is passed to one of the aliases, the script displays up to 100 lines of text from the end of the file that match the string. If no argument is supplied, the script defaults to printing the last 20 lines from the communication log.
### Doors
db - bash last seen door.
dc - close last seen door.
do - open last seen door.
dp - pick last seen door.
du - unlock last seen door.
autoopen [on|off) - If turned *on*, will automatically open doors that you run into. If no argument is supplied, will toggle auto-open from the last known state.
### Grouping
lf - follow leader
lp - protect leader
lr - rescue leader
lt [string] - tell leader string
lw - whois leader
fs - follow self
leader [clear|name] - Manually sets your leader to the given name. If 'clear' is supplied instead of a name, the current leader is forgotten. If no argument is supplied, will print the current leader (if any).
autoride [on|off] - If turned *on*, will automatically ride and lead your mount when your leader rides/leads, and will automatically stand, lead, and ride your mount when you 'ZBLAM'. If no argument is supplied, will toggle auto-ride from the last known state.
autogroup [on|off] - If turned *on*, will automatically 'group' players when they raise their hand. Make sure to turn it *off* when everyone has been grouped. If no argument is supplied, will toggle auto-group from the last known state.
### Hunting
rr - (for manual recovery and looting of arrows) get all.arrow all.corpse, get all.arrow, put all.arrow quiver
rq - reveal quick
rt - reveal thorough
sq - search quick
st - search thorough
b. or bb - bash target
bf - bash target, flee
bs. or j - backstab target
c. - consider target
e. - examine target
s. - shoot target
sf - shoot target, flee
t. - track target
w. - where target
k. or kk - kill target
kf - kill target, flee
kb - kill *bear*
ke - kill *elf*
khe - kill *half-elf*
kd - kill *dwarf*
kh - kill *hobbit*
km - kill *man*
ko - kill *orc
kt - kill *troll*
ttf - (target fighting) target the player or mob who you are currently fighting
tta - (target again) If you previously targeted a brigand and he dies, the tta alias will label the next brigand in the room 't'.
ttc - clears your target
ttt - target the previously marked opponent that has the label 't'
ttb - target *bear*
ttd - target *dwarf*
tte - target *elf*
tthe - target *half-elf*
tth - target *hobbit*
ttm - target *man*
tto - target *orc*
ttr - target *troll*
### Mapper
rinfo [label|vnum] - Returns information about a room. If no room label or vnum is given, will return information about the current room.
rlabel [add|delete|info] [label] [vnum] - Adds, deletes, or returns information for a room label. A vnum argument is only needed when adding a room.
run [c|label|vnum] [arguments] - Determines the most optimal route to the given room, and starts walking you there. If 'c' is given instead of a valid room label or vnum, your last destination will be used. Arguments are optional, and should be separated by a '|' character. If the argument is the word 'no' and a terrain, an extra movement cost of 10 will be added to all rooms with that terrain when calculating the path. Example: 'run seekspot noroad|nobrush' to run to the room labeled 'seekspot' while avoiding brush and roads.
stop - Cancels the auto-walking of the 'run' command.
savemap - saves the loaded map file to disk.
sync [label|vnum] - Manually sync the map to the given room label or vnum. if no label or vnum is given, the 'sync' command will set the mapper's synced state to unsynced, and send a 'look' command to the game.
### Path Walker
p [direction] - If you are are on a road, will start following the road in the given direction using the '=' signs around road exits in the exits line. The script will stop walking if there are more then 1 possible road out of the room, not including the direction you came from (I.E. a junction).
pp - If you are currently following a road, will stop following it.
### Reenter
v - If you successfully fled out of a room, this command will move your character back in the room. Useful for switching tanks when XPing. The command will only work once between successful flees to prevent you from going in the target room's direction twice.
### Report
tnl - Displays how many XP and TP points you need to level.
rpscore - Reports your current HP, Mana, and Movement points to the room, including the percentages.
rptnl - Reports how many XP and TP points you need to level to the room.
rpf - (Report full) same as rpscore, rptnl
### Secret Exits
dadd [secret name] [direction] - Add a secret exit to the current room in the secrets database.  For example: 'dadd colvert e'. Short forms of directions [e|ea|eas] will automatically be converted to their long form 'east'.
ddel [room name|all] [direction|all] - Deletes 1 or more secret exits from the room. Like the 'dadd' command, direction names are automatically converted to their long forn. The word 'all' is a wild card. If there are no more secret exits for the current room after the deletion, the room is automatically removed from the database. Examples: 'ddel wall e' (delete the secret named 'wall' that's to the 'east', but leave the wall that's too the north), 'ddel all e' (delete all secret exits in the room that are located to the east), 'ddel stonedoor all' (Delete all secrets named 'stonedoor' from the room, no matter what direction they are located), 'ddel all all' (delete all the secrets from the room, and remove the room entry from the database).
ddis [string] - Displays all the secrets (if any) for a room or rooms. If the user provides a string to be searched for, a case-insensitive, fuzzy search is performed for all room names in the database matching string. Otherwise, a case-sensitive, exact search is performed for the last captured room name from the mud.
ddo - Open all secret exits in the current room.
### Sounds
playsound [file|directory] - Play a sound file from the 'sounds' directory. If a file name is given, it will be played in the background. If a directory name is given instead, a random file will be played from that directory. Examples: 'playsound tells.wav' (play the file located at 'sounds/tells.wav'), 'playsound combat' (play a random sound file from 'sounds/combat/')
stopsound [file] - Stop playing 1 or more sounds. If a filename is given, only that sound will be stopped. If no arguments are given, all currently playing sounds will be stopped.
mutesound - Toggles the muting of sounds.
vol [up|down] - increases or decreases the volume of all sounds.
### Time
ti - Displays information about the current game time.
nti - Narrates information about the current game time.
sti - Says information about the current game time.
### XP Counter
xp - Shows the XP counter.
### Miscellaneous
bpouch - (substitute the boots that you are currently wearing with the boots in your pouch.) remove boots, get boots pouch, wear boots, put boots pouch
cpouch - (substitute the fur or cloak that you are currently wearing with the cloak in your pouch.) remove cloak, remove fur, get cloak pouch, wear cloak, put cloak pouch, put fur pouch
cpack - (substitute the fur or cloak that you are currently wearing with the cloak in your pack.) remove cloak, remove fur, get cloak pack, wear cloak, put cloak pack, put fur pack
fpack - (substitute the fur or cloak that you are currently wearing with the fur in your pack.) remove cloak, remove fur, get fur pack, wear fur, put cloak pack, put fur pack
initchar - initialize color, prompt, word wrap, spam, brief, and compact settings for your character. This needs to be done once per character for these scripts to work.
ws - wake, stand
