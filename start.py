#!/usr/bin/env python

import argparse
import logging
import sys
import traceback

import mapper.main
import mapper.emulation

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="The accessible Mume mapper.")
	parser.add_argument("-e", "--emulation", help="Start in emulation mode.", action="store_true")
	group = parser.add_mutually_exclusive_group()
	group.add_argument("-g", "--gui", help="Use the GUI (requires pyglet).", action="store_true", default=None)
	group.add_argument("-t", "--text", help="Text-only mode (no GUI).", action="store_false", default=None)
	parser.add_argument("-f", "--format", help="Select how data from the server is transformed before  being sent to the client.", choices=["normal", "tintin", "raw"], default="normal")
	args = parser.parse_args()
	try:
		if args.emulation:
			mapper.emulation.main(use_gui=args.gui or args.text)
		else:
			mapper.main.main(outputFormat=args.format.lower(), use_gui=args.gui or args.text)
	except:
		traceback.print_exception(*sys.exc_info())
		logging.exception("OOPS!")
	finally:
		logging.info("Shutting down.")
		logging.shutdown()
