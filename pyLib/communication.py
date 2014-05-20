from tintin import TinTin

def review(channel, text=""):
	try:
		with open("communication/%s.txt"%channel, "rb") as f:
			data = f.readlines()
	except IOError as e:
		TinTin.echo("%s: '%s'" % (e.strerror, e.filename), "mume")
	text = text.strip()
	if not data:
		output = ["%s log is empty!" % channel.capitalize()]
	elif text.isdigit() and int(text)>=1:
		output = data[-int(text):]
	elif not text.isdigit() and text!="":
		output = [line for line in data if text in line.lower()]
	else:
		output = data[-20:]
	if not output:
		output = ["Nothing found!"]
	for line in output[-100:]:
		TinTin.echo(line.strip(), "mume")
