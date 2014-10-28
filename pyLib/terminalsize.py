#!/usr/bin/env python

# This module adapted from:
# https://gist.github.com/1108174.git

import os
import platform
import shlex
import struct
import subprocess


OS_NAME = platform.system()

if OS_NAME == "Windows":
	import ctypes
else:
	try:
		import fcntl
	except ImportError as e:
		fcntl = None
	try:
		import termios
	except ImportError as e:
		termios = None


def get_terminal_size():
	"""getTerminalSize()
		- get width and height of console
		- works on linux,os x,windows,cygwin(windows)
		originally retrieved from:
		http://stackoverflow.com/questions/566746/how-to-get-console-window-width-in-python
	"""
	tuple_xy = None
	if OS_NAME == "Windows":
		tuple_xy = _get_terminal_size_windows()
	elif OS_NAME in ["Linux", "Darwin"] or OS_NAME.startswith("CYGWIN"):
		tuple_xy = _get_terminal_size_linux()
	elif tuple_xy is None:
		tuple_xy = _get_terminal_size_tput()
	if tuple_xy is None:
		tuple_xy = (80, 24)
	return tuple_xy


def _get_terminal_size_windows():
	if not hasattr(ctypes, "windll"):
		return None
	# stdin handle is -10
	# stdout handle is -11
	# stderr handle is -12
	h = ctypes.windll.kernel32.GetStdHandle(-12)
	csbi = ctypes.create_string_buffer(22)
	res = ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
	if res:
		(bufx, bufy, curx, cury, wattr,\
			left, top, right, bottom,\
			maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
		sizex = right - left + 1
		sizey = bottom - top + 1
		return sizex, sizey


def _get_terminal_size_tput():
	"""get terminal width
		src: http://stackoverflow.com/questions/263890/how-do-i-find-the-width-height-of-a-terminal-window
	"""
	try:
		cols = int(subprocess.check_call(shlex.split('tput cols')))
		rows = int(subprocess.check_call(shlex.split('tput lines')))
		return (cols, rows)
	except:
		return None


def ioctl_GWINSZ(fd):
	if fcntl and termios:
		try:
			return struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, "1234"))
		except:
			return None


def _get_terminal_size_linux():
	cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
	if not cr:
		try:
			fd = os.open(os.ctermid(), os.O_RDONLY)
			cr = ioctl_GWINSZ(fd)
			os.close(fd)
		except:
			pass
	if not cr:
		try:
			cr = (os.environ['LINES'], os.environ['COLUMNS'])
		except:
			return None
	return int(cr[1]), int(cr[0])


if __name__ == "__main__":
	x, y = get_terminal_size()
	print("width = {0}, height = {1}.".format(x, y))
