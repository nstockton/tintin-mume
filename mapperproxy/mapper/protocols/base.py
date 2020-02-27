# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging

# Local Modules:
from ..mapper import MUD_DATA
from ..utils import escapeIAC, unescapeXML


logger = logging.getLogger(__name__)


class BaseProtocolHandler(object):
	def __init__(
			self,
			processed=None,
			remoteSender=None,
			eventSender=None,
			outputFormat=None,
			promptTerminator=None
	):
		self._processed = bytearray() if processed is None else processed
		self._remoteSender = bytearray() if remoteSender is None else remoteSender
		self._eventSender = list() if eventSender is None else eventSender
		self._outputFormat = outputFormat
		self._promptTerminator = promptTerminator

	def _sendRemote(self, dataBytes, raw=False):
		if not raw:
			dataBytes = escapeIAC(dataBytes)
		try:
			self._remoteSender(dataBytes)
		except TypeError:
			if isinstance(self._remoteSender, (bytearray, list)):
				self._remoteSender.extend(dataBytes)
			else:
				raise

	def _sendEvent(self, event, data):
		try:
			self._eventSender((MUD_DATA, (event, unescapeXML(data, True))))
		except TypeError:
			if isinstance(self._eventSender, list):
				self._eventSender.append((MUD_DATA, (event, unescapeXML(data, True))))
			else:
				raise

	def close(self, *args, **kwargs):
		pass

	def parse(self, *args, **kwargs):
		pass
