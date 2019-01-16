# Tileset for the sighted GUI

This directory contains the tileset for the sighted GUI. By default,
a 32 color tileset is used (tiles-multi.xcf), but a 5 color tileset, which has
its own kind of look and feel is also available (tiles-mono.xcf).

![screenshot-multi](screenshot-multi.png?raw=true "screenshot of the 32 colors sighted gui")

![screenshot-mono](screenshot-mono.png?raw=true "screenshot of the 5 colors sighted gui")

# License

The files in this directory are distributed under the license [CC-BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/legalcode).
They are a modified version of [fantasy-tileset.png](https://opengameart.org/content/32x32-fantasy-tileset) originaly created by [Jerome](http://jerom-bd.blogspot.fr/)

The colored version uses the [DB32+Zs8](https://opengameart.org/content/lots-of-trees-and-plants-from-oga-db32-tilesets-pack-1) color palette, created by [zabin](http://duskrpg.blogspot.com/). It is distributed under the licenses [CC-BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/legalcode) and [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode).


# Modifying

You can use [gimp](http://gimp.org) to edit the file tiles.xcf and adapt the tiles to your wishes.

The makefile will help you build the tileset. For that purpose, you will need xcf2png, from [xcftools](http://henning.makholm.net/software), and convert, from [imagemagick](http://www.imagemagick.org/). If you are using the 32 color tileset, just use `make`. Edit the makefile if you want to use the monochromatic color tileset.


