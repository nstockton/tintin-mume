# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import threading


class Timer(threading.Thread):
	def __init__(self, interval, function, *args, **kwargs):
		threading.Thread.__init__(self)
		self.daemon = True
		self.interval = interval
		self.function = function
		self.args = args
		self.kwargs = kwargs
		self.finished = threading.Event()

	def cancel(self):
		self.finished.set()

	def run(self):
		self.finished.wait(self.interval)
		if not self.finished.is_set():
			self.function(*self.args, **self.kwargs)


class RepeatingTimer(threading.Thread):
	def __init__(self, interval, function, *args, **kwargs):
		threading.Thread.__init__(self)
		self.daemon = True
		self.interval = interval
		self.function = function
		self.args = args
		self.kwargs = kwargs
		self.finished = threading.Event()

	def cancel(self):
		self.finished.set()

	def run(self):
		while not self.finished.is_set():
			self.finished.wait(self.interval)
			if not self.finished.is_set():
				self.function(*self.args, **self.kwargs)
