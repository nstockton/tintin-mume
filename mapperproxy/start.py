#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import sys
import traceback

import mapper.main
import mapper.emulation

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="The accessible Mume mapper.")
	parser.add_argument("-e", "--emulation", help="Start in emulation mode.", action="store_true")
	parser.add_argument("-i", "--interface", help="Select a user interface.", choices=["text", "hc", "sighted"], default="text")
	parser.add_argument("-f", "--format", help="Select how data from the server is transformed before  being sent to the client.", choices=["normal", "tintin", "raw"], default="normal")
	args = parser.parse_args()
	try:
		if args.emulation:
			mapper.emulation.main(interface=args.interface)
		else:
			mapper.main.main(outputFormat=args.format.lower(), interface=args.interface)
	except:
		traceback.print_exception(*sys.exc_info())
		logging.exception("OOPS!")
	finally:
		logging.info("Shutting down.")
		logging.shutdown()
