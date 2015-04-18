def decodeBytes(bytes):
	try:
		return bytes.decode("utf-8")
	except UnicodeDecodeError:
		return bytes.decode("latin-1")
	except AttributeError:
		return ""
