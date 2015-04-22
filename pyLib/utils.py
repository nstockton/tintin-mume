from .mapperconstants import IS_PYTHON_2


IAC = 0xff
DONT = 0xfe
DO = 0xfd
WONT = 0xfc
WILL = 0xfb
NULL = 0x00
SB = 0xfa
SE = 0xf0
GA = 0xf9

def decodeBytes(data):
	try:
		return data.decode("utf-8")
	except UnicodeDecodeError:
		return data.decode("latin-1")
	except AttributeError:
		return ""

class TelnetStripper(object):
	"""Strip Telnet option sequences from data"""

	def __init__(self):
		self.buffer = bytearray()
		self.inIAC = False
		self.inSubOption = False

	def process(self, data):
		for byte in data:
			# in Python 2, byte will be an str type, while in Python 3, byte will be an int type.
			if IS_PYTHON_2:
				byte = ord(byte)
			if not self.inIAC:
				if byte == IAC:
					self.inIAC = True
				elif not self.inSubOption and byte not in (NULL, 0x11):
					self.buffer.append(byte)
			else:
				if byte in (DO, DONT, WILL, WONT):
					# This is the second byte in a 3-byte telnet option sequence.
					# Skip the byte, and move on to the next.
					continue
				# From this point on, byte is the final byte in a 2-3 byte telnet option sequence.
				self.inIAC = False
				if byte == SB:
					# Sub-option negotiation begin
					self.inSubOption = True
				elif byte == SE:
					# Sub-option negotiation end
					self.inSubOption = False
				elif self.inSubOption:
					# Ignore subsequent bytes until the sub option negotiation has ended.
					continue
				elif byte == IAC:
					# This is an escaped IAC byte to be added to the buffer.
					self.buffer.append(byte)
				elif byte == GA:
					# Mume sends an IAC-GA sequence after every prompt.
					# This is a good time to return and clear the buffer.
					result = bytes(self.buffer)
					del self.buffer[:]
					return result
		# If we're here, all the data bytes have been consumed, and we haven't received an IAC-GA sequence yet.
		return None
