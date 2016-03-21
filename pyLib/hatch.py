from .tintin import TinTin

permutations = {
  'N': [('Forostar', 'north'), ('Orrostar', 'east'), ('Hyarrostar', 'southeast'), ('Hyarnustar', 'southwest'), ('Andustar', 'west')],
  'E': [('Andustar', 'north'), ('Forostar', 'east'), ('Orrostar', 'southeast'), ('Hyarrostar', 'southwest'), ('Hyarnustar', 'west')],
  'SE': [('Hyarnustar', 'north'), ('Andustar', 'east'), ('Forostar', 'southeast'), ('Orrostar', 'southwest'), ('Hyarrostar', 'west')],
  'SW': [('Hyarrostar', 'north'), ('Hyarnustar', 'east'), ('Andustar', 'southeast'), ('Forostar', 'southwest'), ('Orrostar', 'west')],
  'W': [('Orrostar', 'north'), ('Hyarrostar', 'east'), ('Hyarnustar', 'southeast'), ('Andustar', 'southwest'), ('Forostar', 'west')],
}

def send_dirs(d):
  p = permutations.get(d.upper(), None)
  if not p:
    TinTin.echo("Haven't heard of a direction named {0}.  Try N, E, S, W, SE, or SW".format(d), 'mume')
    return
  for move in p:
    TinTin.send('move {0} {1}'.format(move[0], move[1]), 'mume')
  TinTin.send('move mittalmar centre', 'mume')
