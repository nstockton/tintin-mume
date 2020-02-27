# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import unittest
from unittest.mock import call, Mock, patch

from mapper.mapper import Mapper, MUD_DATA, USER_DATA


class TestMapper(unittest.TestCase):
	def setUp(self):
		Mapper.loadRooms = Mock()  # to speed execution of tests
		self.mapper = Mapper(
			client=Mock(),
			server=None,
			outputFormat=None,
			interface="text",
			promptTerminator=None,
			gagPrompts=None,
			findFormat=None,
			isEmulatingOffline=None,
		)
		self.mapper.daemon = True  # this allows unittest to quit if the mapper thread does not close properly.

	def testMapper_run(self):
		self.mapper.handleUserData = Mock()
		self.mapper.handleMudEvent = Mock()
		self.mapper.clientSend = Mock()
		self.mapper.start()

		# feed data into the mapper queue
		for dataType, data in [
			(MUD_DATA, ("line", b"Welcome to mume")),
			(MUD_DATA, ("prompt", b"hp:hurt mana:burning>")),
			(USER_DATA, b"rinfo"),
			(USER_DATA, b"emu go lorien"),
			(USER_DATA, b"not_a_user_command"),
			(MUD_DATA, ("movement", b"east")),
			(USER_DATA, b"run ingrove"),
			(MUD_DATA, ("not_an_event", b"good bype world")),
			(None, None),
		]:
			self.mapper.queue.put((dataType, data))

		# insure that the mapper closes properly
		self.mapper.join(1)
		self.assertFalse(self.mapper.is_alive(), "mapper thread took longer than a second to quit")
		self.assertTrue(self.mapper.queue.empty(), "mapper queue is not empty after thread termination")

		# validate calls to handleUserData
		userCalls = self.mapper.handleUserData.mock_calls
		self.assertEqual(len(userCalls), 4)
		self.assertEqual(userCalls[0], call(b"rinfo"), "First call to handleUserData was not as expected.")
		self.assertEqual(userCalls[1], call(b"emu go lorien"), "Second call to handleUserData was not as expected.")
		self.assertEqual(userCalls[2], call(b"not_a_user_command"), "Third handleUserData was not as expected.")
		self.assertEqual(userCalls[3], call(b"run ingrove"), "Fourth call to handleUserData was not as expected.")

		# validate calls to handleMudEvent
		serverCalls = self.mapper.handleMudEvent.mock_calls
		self.assertEqual(len(serverCalls), 4)
		self.assertEqual(serverCalls[0], call("line", b"Welcome to mume"), "handleMudEvent #0 not expected.")
		self.assertEqual(serverCalls[1], call("prompt", b"hp:hurt mana:burning>"), "Second handleMudEvent")
		self.assertEqual(serverCalls[2], call("movement", b"east"), "Third handleMudEvent not as expected")
		self.assertEqual(serverCalls[3], call("not_an_event", b"good bype world"), "Fourth handleMudEvent")

	def testMapper_handleUserData(self):
		handleUserData = self.mapper.handleUserData

		for command, handlerName, args in [
			(b"rinfo", "user_command_rinfo", ""),
			(b"rlabel add here", "user_command_rlabel", "add here"),
			(b"emu go emoria", "user_command_emu", "go emoria"),
		]:
			with patch.object(self.mapper, handlerName) as handler:
				handleUserData(command)
				handler.assert_called_with(args)

		for command in [
			b"not_a_command",
			b"test failure",
			b"rinf",
		]:
			with self.assertRaises(AttributeError):
				self.mapper.handleUserData(command)


class TestMapper_handleMudEvent(unittest.TestCase):
	def setUp(self):
		Mapper.loadRooms = Mock()  # to speed execution of tests
		self.legacyHandlerNames = [
			handlerName for handlerName in dir(Mapper)
			if handlerName.startswith("mud_event_") and callable(getattr(Mapper, handlerName))
		]
		for handlerName in self.legacyHandlerNames:
			setattr(Mapper, handlerName, Mock())
		self.mapper = Mapper(
			client=Mock(),
			server=None,
			outputFormat=None,
			interface="text",
			promptTerminator=None,
			gagPrompts=None,
			findFormat=None,
			isEmulatingOffline=None,
		)
		self.mapper.daemon = True  # this allows unittest to quit if the mapper thread does not close properly.

	def test_legacyMudEventHandlers(self):
		events = [handlerName[len("mud_event_"):] for handlerName in self.legacyHandlerNames]
		handlers = [getattr(self.mapper, handlerName) for handlerName in self.legacyHandlerNames]
		for event, handler in zip(events, handlers):
			sampleInput1 = b"Helol oje"
			sampleInput2 = b"no sir, away. a papaya war is on"
			sampleInput3 = b"delting no sir, away. a papaya war is on"
			self.mapper.registerMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput1)
			handler.assert_called_once_with(str(sampleInput1, "US-ASCII"))
			handler.reset_mock()
			self.mapper.handleMudEvent(event, sampleInput2)
			handler.assert_called_once_with(str(sampleInput2, "US-ASCII"))
			handler.reset_mock()
			self.mapper.deregisterMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput3)
			handler.assert_not_called()

	def test_newMudEventHandlers(self):
		for event in [
			"sillyEvent",
			"room",
			"otherEvent",
		]:
			handler = Mock()
			sampleInput1 = b"Helol oje"
			sampleInput2 = b"no sir, away. a papaya war is on"
			sampleInput3 = b"delting no sir, away. a papaya war is on"
			self.mapper.registerMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput1)
			handler.assert_called_once_with(str(sampleInput1, "US-ASCII"))
			handler.reset_mock()
			self.mapper.handleMudEvent(event, sampleInput2)
			handler.assert_called_once_with(str(sampleInput2, "US-ASCII"))
			handler.reset_mock()
			self.mapper.deregisterMudEventHandler(event, handler)
			self.mapper.handleMudEvent(event, sampleInput3)
			handler.assert_not_called()

	def test_handleMudEvent_failsGracefullyWhenHandlingAnUnknownEvent(self):
		for unknownEvent in [
			"unkk",
			"New_game_event",
			"room",
			"<interesting-tag-<in>-a-tag>",
		]:
			self.mapper.handleMudEvent(unknownEvent, "meaningless input")
			# simply require this to execute without raising an exception
