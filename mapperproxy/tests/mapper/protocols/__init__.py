# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


def parseMudOutput(handler, dataBytes):
	result = bytearray()
	for ordinal in dataBytes:
		value = handler.parse(ordinal)
		if value is not None:
			result.append(value)
	return result
