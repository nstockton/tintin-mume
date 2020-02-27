# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from abc import ABC, abstractmethod


class Handler(ABC):
	def __init__(self, mapper, event=None):
		"""Initialises a mud event handler in the given mapper class.
		params: mapper, event
		where mapper is the mapper instance that will be dispatching events,
		and event is an optional event name.
		The event name may be omitted if the subclass is defined with an event attribute.
		"""
		self.mapper = mapper
		try:
			self.event = event or self.event
		except AttributeError as e:
			raise ValueError(
				"Tried to initialise handler without an event type."
				" Either pass event=MyEventType when initialising, or declare self.event in the class definition."
			) from e
		self.mapper.registerMudEventHandler(self.event, self.handle)

	def __del__(self):
		if hasattr(self, "event"):
			self.mapper.deregisterMudEventHandler(self.event, self.handle)

	@abstractmethod
	def handle(self, data):
		"""the method called when the event is dispatched"""
		pass
