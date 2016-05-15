#!/usr/bin/env python

import sys

import mapper.main

if __name__ == "__main__":
	if sys.argv:
		outputFormat = sys.argv[-1].strip().lower()
		if outputFormat not in ("normal", "tintin", "raw"):
			outputFormat = "normal"
	else:
		outputFormat = "normal"
	mapper.main.main(outputFormat)
