# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
from .config import Config, config_lock

with config_lock:
	cfg = Config()
	try:
		debug_level = cfg["debug_level"]
		if debug_level not in logging._levelNames:
			if isinstance(debug_level, int):
				if debug_level * 10 in logging._levelNames:
					debug_level *= 10
				elif debug_level - debug_level % 10 in logging._levelNames:
					debug_level -= debug_level % 10
				else:
					debug_level = None
			else:
				debug_level = debug_level.upper()
		if not isinstance(debug_level, int):
			debug_level = logging._levelNames[debug_level]
	except (KeyError, AttributeError):
		debug_level = None
	finally:
		if "debug_level" not in cfg or debug_level != cfg["debug_level"]:
			cfg["debug_level"] = debug_level
			c.save()
	del cfg

if debug_level is not None or debug_level != 0:
	logging.basicConfig(filename="debug.log", filemode="w", level=debug_level, format="%(levelname)s: from %(name)s in %(threadName)s: \"%(message)s\" @ %(asctime)s.%(msecs)d", datefmt="%m/%d/%Y %H:%M:%S")
	logging.info("Initializing")
else:
	del logging
