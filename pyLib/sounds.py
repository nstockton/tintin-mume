import os
import random

from .tintin import TinTin

try:
	from pygame import mixer
except ImportError:
	TinTin.echo("Unable to import pyGame: please make sure it is installed.", "gts")
	mixer = None

SOUNDS_DIRECTORY = "sounds"


class Sounds(object):
	def __init__(self):
		self.soundObjects = {}
		self.muted = False

	def play(self, fileName="", volume="100"):
		fileName = fileName.strip()
		if self.muted or not fileName or mixer is None:
			return
		if not volume.isdigit():
			return TinTin.echo("Invalid volume: only numbers 1-100 are allowed.", "mume")
		volume = int(volume) / 100.0
		path = os.path.join(SOUNDS_DIRECTORY, fileName)
		if os.path.isdir(path):
			fileName = random.choice(os.listdir(path))
			path = os.path.join(path, fileName)
		if not fileName in self.soundObjects:
			if os.path.exists(path):
				self.soundObjects[fileName] = mixer.Sound(path)
			else:
				return TinTin.echo("No such sound", "mume")
		self.soundObjects[fileName].set_volume(volume)
		self.soundObjects[fileName].play()

	def stop(self, fileName=""):
		if mixer is None:
			return
		fileName = fileName.strip()
		if fileName:
			if fileName in self.soundObjects:
				self.soundObjects[fileName].stop()
				del self.soundObjects[fileName]
			else:
				TinTin.echo("that sound has not been loaded!", "mume")
		else:
			for soundObj in self.soundObjects:
				self.soundObjects[soundObj].stop()
			self.soundObjects.clear()

	def mute(self):
		if mixer is None:
			return
		self.muted = self.muted == False
		if self.muted:
			self.stop()
		TinTin.echo("sound {0}.".format("muted" if self.muted else "unmuted"), "mume")

	def load(self):
		if mixer is not None:
			mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

	def unload(self):
		if mixer is not None:
			mixer.quit()
