# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from unittest.mock import Mock

from mapper.mapper import Mapper
from mapper.mudevents import Handler


class DummieHandler(Handler):
	event = "testEvent"

	def handle(self, data):
		self.mapper.queue.put("I received " + data)


class HandlerWithoutType(Handler):
	def handle(self, data):
		pass


class TestHandler(unittest.TestCase):
	def setUp(self):
		Mapper.loadRooms = Mock()  # to speed execution of tests
		self.mapper = Mapper(
			client=None,
			server=None,
			outputFormat=None,
			interface="text",
			promptTerminator=None,
			gagPrompts=None,
			findFormat=None,
			isEmulatingOffline=None,
		)
		self.mapper.daemon = True  # this allows unittest to quit if the mapper thread does not close properly.

	def testMapper_handle(self):
		queue = self.mapper.queue
		queue.put = Mock()
		dummieHandler = DummieHandler(self.mapper)

		self.mapper.handleMudEvent(dummieHandler.event, b"Hello world")
		queue.put.assert_called_once_with("I received Hello world")
		queue.put.reset_mock()

		self.mapper.handleMudEvent("testEvent", b"I am here.")
		queue.put.assert_called_once_with("I received I am here.")
		queue.put.reset_mock()

		dummieHandler.__del__()
		self.mapper.handleMudEvent("testEvent", b"Goodbye world")
		queue.put.assert_not_called()

	def test_init_raisesValueErrorWhenNoEventTypeIsProvided(self):
		self.assertRaises(ValueError, HandlerWithoutType, self.mapper)
