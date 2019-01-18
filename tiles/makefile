# Uncomment your desired color
COLOR=multi
#COLOR=blue
#COLOR=green
#COLOR=gold

# Uncomment your desired player tile
PLAYER=helf-light
#PLAYER=cleric
#PLAYER=warrior
#PLAYER=orc
#PLAYER=troll

TILES= armour attention brush cavern city \
exitdown exitup field forest guild herb \
hill indoor key mountain quest \
random rapid rent road shop smob swamp \
treasure tunnel undefined underwater \
walleast wallnorth wallsouth wallwest \
water weapon elf cleric warrior orc troll \
helf-light helf-dark

all: $(TILES:%=%.png) player.png

%.png: %-$(COLOR).png
	mv $< $@

player.png: $(PLAYER).png
	ln -sf $< $@

%-multi.png: %
	xcf2png tiles-multi.xcf $< > $@

%-blue.png: %
	xcf2png tiles-mono.xcf $< > $@

%-green.png: %-5.png
	convert $< -fill '#204631' -opaque '#1A2B2F'\
		-fill '#527F39' -opaque '#273F45'\
		-fill '#AEC440' -opaque '#4D767E'\
		-fill '#D7E894' -opaque '#7CC5D2' $@

%-gold.png: %-5.png
	convert $< -fill '#2F0E09' -opaque '#1A2B2F'\
		-fill '#4B2C0D' -opaque '#273F45'\
		-fill '#826418' -opaque '#4D767E'\
		-fill '#DCC32C' -opaque '#7CC5D2' $@

clean:
	rm -f $(TILES:%=%.png) player.png

.PHONY: $(TILES)

