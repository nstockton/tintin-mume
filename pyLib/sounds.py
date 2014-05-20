import os
import random

from tintin import TinTin

try:
	from pygame import mixer
except ImportError:
	TinTin.echo("Unable to import pyGame: please make sure it is installed.", "gts")
	mixer = None


SOUNDS_DIR = "sounds"

sounds = {}
muted = False


def play(filename="", volume="100"):
	global sounds
	filename = filename.strip()
	if muted or not filename or not mixer:
		return
	if not volume.isdigit():
		return TinTin.echo("Invalid volume: only numbers 1-100 are allowed.", "mume")
	volume = int(volume) / 100.0
	path = os.path.join(SOUNDS_DIR, filename)
	if os.path.isdir(path):
		filename = random.choice(os.listdir(path))
		path = os.path.join(path, filename)
	if not filename in sounds:
		if os.path.exists(path):
			sounds[filename] = mixer.Sound(path)
		else:
			return TinTin.echo("No such sound", "mume")
	sounds[filename].set_volume(volume)
	sounds[filename].play()

def stop(filename=""):
	global sounds
	if not mixer:
		return
	filename = filename.strip()
	if filename:
		if filename in sounds:
			sounds[filename].stop()
			del sounds[filename]
		else:
			TinTin.echo("that sound has not been loaded!", "mume")
	else:
		for sound in sounds:
			sounds[sound].stop()
		sounds.clear()

def mute():
	global muted
	if not mixer:
		return
	muted = muted==False
	if muted:
		stop()
	TinTin.echo("sound %s." % "muted" if muted else "unmuted", "mume")

def load():
	if not mixer:
		return
	mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

def unload():
	if not mixer:
		return
	mixer.quit()
