# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Built-in Modules:
import logging

# Local Modules:
from .base import BaseProtocolHandler
from .telnet import TelnetHandler
from .mpi import MPIHandler
from .xml import XMLHandler
from ..utils import unescapeXML


logger = logging.getLogger(__name__)
__all__ = ["ProtocolHandler"]


class ProtocolHandler(BaseProtocolHandler):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._telnet = TelnetHandler(processed=self._processed, *args, **kwargs)
		self._mpi = MPIHandler(processed=self._processed, *args, **kwargs)
		self._xml = XMLHandler(processed=self._processed, *args, **kwargs)
		self.handlers = [
			self._telnet,
			self._mpi,
			self._xml
		]

	def close(self):
		for handler in self.handlers:
			handler.close()

	__del__ = close

	def notify(self, value):
		for item in value:
			for handler in self.handlers:
				try:
					item = handler.parse(item)
				except TypeError:
					for ordinal in bytes(item):
						item = handler.parse(ordinal)
				if item is None:
					break

	def parse(self, dataBytes):
		self.notify(dataBytes)
		result = bytes(self._processed)
		self._processed.clear()
		return result if self._outputFormat == "raw" else unescapeXML(result, True)
