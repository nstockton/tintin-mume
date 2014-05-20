class TinTin(object):
	@staticmethod
	def execute(command, session="gts"):
		print "tintin_execute(%s) %s" % (session, command)

	@staticmethod
	def ticker(name, command, seconds, session="gts"):
		print "tintin_ticker (%s) (%s) (%s) (%s)" % (session, name, command, seconds)

	@staticmethod
	def delay(name, command, seconds, session="gts"):
		print "tintin_delay (%s) (%s) (%s) (%s)" % (session, name, command, seconds)

	@staticmethod
	def var(name, value, session="gts"):
		print "tintin_var (%s) (%s) (%s)" % (session, name, value)

	@staticmethod
	def send(command, session="gts"):
		print "tintin_send (%s) %s" % (session, command)

	@staticmethod
	def showme(command, session="gts"):
		print "tintin_showme (%s) %s" % (session, command)

	@staticmethod
	def echo(*args):
		if len(args) >= 2:
			session = args[-1]
			commands = ["(%s)"%command for command in args[:-1]]
		else:
			session = "gts"
			commands = ["(%s)"%command for command in args]
		commands = "%s%s" % (" ".join(commands), " ()" * (20-len(commands)))
		print "tintin_echo (%s) %s" % (session, commands)
