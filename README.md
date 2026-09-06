<p align="center"><img src="data/input-remapper.svg" width=100/></p>

<h1 align="center">Input Remapper</h1>

<p align="center">
  An easy to use tool for Linux to change the behaviour of your input devices.<br/>
  Supports X11, Wayland, combinations, programmable macros, joysticks, wheels,<br/>
  triggers, keys, mouse-movements and more. Maps any input to any other input.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="readme/macros.md">Macros</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="readme/examples.md">Examples</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>


<p align="center">
  <img src="readme/screenshot.png" width="48%"/>
  &#160;
  <img src="readme/screenshot_2.png" width="48%"/>
</p>

<br/>

## Installation

### Ubuntu/Debian

Either download an installable .deb file from the [latest release](https://github.com/sezanzeb/input-remapper/releases):

```sh
wget https://github.com/sezanzeb/input-remapper/releases/download/2.2.1/input-remapper-2.2.1.deb
sudo apt install -f ./input-remapper-2.2.1.deb
```

Or install the very latest changes via:

```sh
sudo apt install git gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper
./scripts/build-deb.sh
sudo apt purge input-remapper input-remapper-daemon input-remapper-gtk python3-inputremapper
sudo apt install -f ./dist/input-remapper-2.2.1.deb
```

Input Remapper is also available in the repositories of [Debian](https://tracker.debian.org/pkg/input-remapper)
and [Ubuntu](https://packages.ubuntu.com/oracular/input-remapper) via

```sh
sudo apt install input-remapper
```

Input Remapper ≥ 2.0 requires at least Ubuntu 22.04.

<br/>

### Fedora

```sh
sudo dnf install input-remapper
sudo systemctl enable --now input-remapper
```

<br/>

### Arch

```sh
yay -S input-remapper-git
sudo systemctl enable --now input-remapper
```

<br/>

### Void

```sh
sudo xbps-install -S input-remapper
sudo ln -s /etc/sv/input-remapper /var/service
sudo sv up input-remapper
```

<br/>

### Other Distros

Figure out the packages providing those dependencies in your distro, and install them:
`python3-evdev` ≥1.3.0, `gtksourceview4`, `python3-devel`, `python3-pydantic`,
`python3-dasbus`, `python3-psutil`

You can also use pip to install some of them. Python packages need to be installed
globally for the service to be able to import them. Don't use `--user`. Conda and such
may also cause problems due to changed python paths and versions.

```sh
sudo pip install evdev pydantic dasbus PyGObject
```

```sh
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper
sudo python3 -m install --root /
sudo systemctl enable --now input-remapper
```

For all other options and help, check `python3 -m install --help`

To uninstall:

```sh
sudo python3 -m install.uninstall
```


## 🌐 Web Resources & Interactive Index
- [WEAPONS AND RAGDOLLS](https://studyplayings.pages.dev/weapons-and-ragdolls.html)
- [SAVE THE PIGGIES](https://themindplay.pages.dev/save-the-piggies.html)
- [FLOWER BLOCK](https://learnquester.github.io/flower-block.html)
- [EATING SIMULATOR](https://learnquester.pages.dev/eating-simulator.html)
- [POP PARTY SUIKA WATERMELON](https://studyplayings.web.app/pop-party-suika-watermelon.html)
- [STICKMAN RAGDOLL PLAYGROUND](https://learnquester.github.io/stickman-ragdoll-playground.html)
- [CATEGORY IBOSS](https://thelearnquester.web.app/category-iboss.html)
- [67 CLICKER](https://learnquester.github.io/67-clicker.html)
- [TRAFFIC TAP PUZZLE](https://learnquester.github.io/traffic-tap-puzzle.html)
- [MAHJONG CRIMES PUZZLE STORY](https://studyplaying.github.io/mahjong-crimes-puzzle-story.html)
- [BLOCK PUZZLE JEWEL FOREST](https://learnquester.pages.dev/block-puzzle-jewel-forest.html)
- [BRAIN PUZZLE TRICKY CHOICES](https://learnquester.github.io/brain-puzzle-tricky-choices.html)
- [JOURNEY OF ESCAPE](https://studyplaying.github.io/journey-of-escape.html)
- [CUBE DROP PUZZLE](https://learnquester.github.io/cube-drop-puzzle.html)
- [UNDERWATER SURVIVAL](https://studyplaying.github.io/underwater-survival.html)
- [YUMMY TALES 4](https://studyplayings.pages.dev/yummy-tales-4.html)
- [PRINCESSES OF QUADROBICS](https://thelearnquester.web.app/princesses-of-quadrobics.html)
- [DESERT ROVER SURVIVAL](https://learnquester.pages.dev/desert-rover-survival.html)
- [CATEGORY BYEPASSHUB](https://studyplayings.pages.dev/category-byepasshub.html)
- [CATEGORY CONTROLLER](https://studyplayings.pages.dev/category-controller.html)
- [CATEGORY BATTLE](https://studyplayings.web.app/category-battle.html)
- [ARCHERS RAGDOLL PHYSICS](https://learnquester.github.io/archers-ragdoll-physics.html)
- [DRIVE IN CINEMA IDLE GAME](https://learnquester.pages.dev/drive-in-cinema-idle-game.html)
- [CYBER HIGHWAY ESCAPE](https://learnquester.pages.dev/cyber-highway-escape.html)
- [CATEGORY CARTOON76](https://studyplayings.pages.dev/category-cartoon76.html)
- [CATEGORY FASHION105](https://studyplayings.pages.dev/category-fashion105.html)
- [MATCH 3 DREAM ROOM](https://studyplayings.web.app/match-3-dream-room.html)
- [WOOP CRAWL UP](https://studyplayings.pages.dev/woop-crawl-up.html)
- [TUNG SAHUR BOTS CHASE ROOM](https://learnquester.pages.dev/tung-sahur-bots-chase-room.html)
- [THE WHITE ROOM 5](https://studyplaying.github.io/the-white-room-5.html)
- [TRAFFIC TAP PUZZLE](https://learnquester.pages.dev/traffic-tap-puzzle.html)
- [ANNAS STORY DRESS UP DIY](https://thelearnquesters.pages.dev/annas-story-dress-up-diy.html)
- [STICK NINJA SURVIVAL](https://learnquesters.pages.dev/stick-ninja-survival.html)
- [THE WALKING DEADBLOCKS](https://thelearnquesters.pages.dev/the-walking-deadblocks.html)
- [DARTS JAM](https://thequizzone.pages.dev/darts-jam.html)
- [MAHJONG CONNECT COOKWARE](https://theskillquest.pages.dev/mahjong-connect-cookware.html)
- [SPRUNKI LAVA ESCAPE 2PLAYER](https://thequizzone.pages.dev/sprunki-lava-escape-2player.html)
- [CAPYBARA BLOCK BLAST](https://studyplaying.github.io/capybara-block-blast.html)
- [CATEGORY INCREMENTAL](https://studyplayings.pages.dev/category-incremental.html)
- [INDEX4](https://studyplayings.web.app/index4.html)
- [TRUE LOVE CALCULATOR NZW](https://thequizzone.pages.dev/true-love-calculator-nzw.html)
- [FARM MATCH SEASONS 3](https://theskillquest.pages.dev/farm-match-seasons-3.html)
- [URBAN ASSAULT FORCE](https://learnquester.github.io/urban-assault-force.html)
- [GUESS THE ITALIAN BRAINROT ANIMALS](https://themindzone.pages.dev/guess-the-italian-brainrot-animals.html)
- [DART HERO](https://theskillquest.pages.dev/dart-hero.html)
- [DIAMOND MOSAIC](https://studyplayings.web.app/diamond-mosaic.html)
- [PYRAMIDZ2](https://learnquester.pages.dev/pyramidz2.html)
- [LITTLE CANDY BAKERY](https://learnquester.github.io/little-candy-bakery.html)
- [CHICKEN WILD RUN](https://thequizzone.pages.dev/chicken-wild-run.html)
- [INDEX37](https://thelearnquesters.pages.dev/index37.html)
- [HELICOPTER BATTLE STEVE 2 PLAYER](https://studyplayings.web.app/helicopter-battle-steve-2-player.html)
- [CATEGORY DRAWING34](https://thelearnquester.web.app/category-drawing34.html)
- [CATEGORY MAHJONG CONNECT 2](https://thequizzone.pages.dev/category-mahjong-connect-2.html)
- [CATEGORY CASUAL 7](https://studyplayings.pages.dev/category-casual-7.html)
- [TAPKO](https://studyplayings.web.app/tapko.html)
- [HIDDEN OBJECT ROOMS EXPLORATION](https://studyplaying.github.io/hidden-object-rooms-exploration.html)
- [CATEGORY CARTOON76](https://thelearnquesters.pages.dev/category-cartoon76.html)
- [MATCH 3 DREAM ROOM](https://themindzone.pages.dev/match-3-dream-room.html)
- [ONLINE PORTAL](https://brainquests.github.io/)
- [ZOMBIE HIGHWAY RAMPAGE](https://themindzone.pages.dev/zombie-highway-rampage.html)
- [CATEGORY AVOID295](https://theskillquest.pages.dev/category-avoid295.html)
- [CATEGORY CASUAL 17](https://thelearnquesters.pages.dev/category-casual-17.html)
- [CATEGORY HORROR](https://iskillquest.pages.dev/category-horror.html)
- [HEROBALL ADVENTURES 2](https://thequizzone.pages.dev/heroball-adventures-2.html)
- [INDEX6](https://quizverses.pages.dev/index6.html)
- [CATEGORY PUZZLE 4](https://themindzone.pages.dev/category-puzzle-4.html)
- [IDLE AIRPORT CEO](https://quizverses.github.io/idle-airport-ceo.html)
- [ROBOT TRANSFORM RACE](https://learnquester.github.io/robot-transform-race.html)
- [ICE FISHING 3D](https://quizverses.pages.dev/ice-fishing-3d.html)
- [MONSTER SLAYERS](https://thelearnquesters.pages.dev/monster-slayers.html)
- [REAL GT RACING SIMULATOR](https://learnquester.pages.dev/real-gt-racing-simulator.html)
- [BEAM DRIVE CAR CRASH TEST SIMULATOR](https://thequizzone.pages.dev/beam-drive-car-crash-test-simulator.html)
- [FALLING ART RAGDOLL SIMULATOR](https://thequizzone.pages.dev/falling-art-ragdoll-simulator.html)
- [DESTRUCTION OF STICKMAN ZOMBIE](https://theskillquest.pages.dev/destruction-of-stickman-zombie.html)
- [LAND CRUISER OFFROAD DRIVER](https://thelearnquesters.pages.dev/land-cruiser-offroad-driver.html)
- [ZOMBIE CONQUER COUNTRIES](https://quizverses.github.io/zombie-conquer-countries.html)
- [SORTING FROGS](https://studyplayings.web.app/sorting-frogs.html)
- [BLOCK MINE FUSE TNT](https://theskillquest.pages.dev/block-mine-fuse-tnt.html)
- [COLOR COCKTAIL](https://learnquester.pages.dev/color-cocktail.html)
- [CATEGORY FREE SOLITAIRE GAMES](https://thelearnquester.web.app/category-free-solitaire-games.html)
- [INDEX27](https://quizverses.github.io/index27.html)
- [DREAM PET HOTEL](https://thequizzone.pages.dev/dream-pet-hotel.html)
- [CIRCLE RUN ENDLESS](https://studyquests.pages.dev/circle-run-endless.html)
- [CATEGORY SOCCER 2](https://thelearnquester.web.app/category-soccer-2.html)
- [ITALIAN BRAINROT QUIZ](https://thequizzone.pages.dev/italian-brainrot-quiz.html)
- [CATEGORY GOGUARDIAN](https://thelearnquester.web.app/category-goguardian.html)
- [BALING BUM](https://thequizzone.pages.dev/baling-bum.html)
- [PUZZLE ABOUT ORANGE](https://learnquester.github.io/puzzle-about-orange.html)
- [CUTE CRAFT LAB](https://studyquesthub.web.app/cute-craft-lab.html)
- [MERGE HAVEN](https://thequizzone.pages.dev/merge-haven.html)
- [STICKMAN PRISON ESCAPE](https://themindzone.pages.dev/stickman-prison-escape.html)
- [RESCUE RIFT](https://thelearnquesters.pages.dev/rescue-rift.html)
- [ONE HERO](https://themindzone.pages.dev/one-hero.html)
- [GALACTIC CRUSADE CLICKER](https://theskillquest.pages.dev/galactic-crusade-clicker.html)
- [ASSOCIATION CONNECT WORD](https://thelearnquesters.pages.dev/association-connect-word.html)
- [ROMANTIC MATCH TACTICS](https://theskillquest.pages.dev/romantic-match-tactics.html)
- [TRICKY LIFE](https://quizverses.github.io/tricky-life.html)
- [UNSCREW WOOD PUZZLE](https://quizverses-9d2f2.web.app/unscrew-wood-puzzle.html)
- [SCHOOL TEACHER SIMULATOR](https://thelearnquesters.pages.dev/school-teacher-simulator.html)
- [SUPER BITCOIN BOY](https://theskillquest.pages.dev/super-bitcoin-boy.html)
- [DR PARKING](https://learnquester.github.io/dr-parking.html)
- [CATEGORY FARMING](https://thelearnquesters.pages.dev/category-farming.html)
- [SPIDERLOX THEME PARK BATTLE](https://thequizzone.pages.dev/spiderlox-theme-park-battle.html)
- [HEXA SORT](https://themindzone.pages.dev/hexa-sort.html)
- [ICE CREAM INC](https://thelearnquesters.pages.dev/ice-cream-inc.html)
- [BUBBLE BLASTERS](https://theskillquest.pages.dev/bubble-blasters.html)
- [BLOCK MASTER SUPER PUZZLE](https://studyplayings.pages.dev/block-master-super-puzzle.html)
- [NINJA DASH COZY TACTIC PUZZLE](https://quizverses.github.io/ninja-dash-cozy-tactic-puzzle.html)
- [CATEGORY STICKMAN](https://studyquesthub.web.app/category-stickman.html)
- [SITEMAP](https://cryptotify.netlify.app/sitemap.html)
- [HIDDEN KITTY](https://quizverses.github.io/hidden-kitty.html)
- [FOOT HOSPITAL](https://studyplaying.github.io/foot-hospital.html)
- [CATEGORY SURVIVAL366](https://thelearnquester.web.app/category-survival366.html)
- [BELOTE 3IN1](https://studyplayings.web.app/belote-3in1.html)
- [HIDDEN OBJECTS ISLAND](https://learnquester.pages.dev/hidden-objects-island.html)
- [OBBY PARKOUR RACING](https://studyplayings.pages.dev/obby-parkour-racing.html)
- [TRALALA CONNECT](https://thelearnquesters.pages.dev/tralala-connect.html)
- [SPRUNKI EASTER COLORING](https://learnquester.github.io/sprunki-easter-coloring.html)
- [CUTE SHEEP SKYBLOCK](https://themindzone.pages.dev/cute-sheep-skyblock.html)
- [SECRETS OF CHARMLAND](https://studyplaying.github.io/secrets-of-charmland.html)
- [SORT MASTER](https://theskillquest.pages.dev/sort-master.html)
- [LIMITED DEFENSE](https://studyplayings.pages.dev/limited-defense.html)
- [CATEGORY FLASH](https://studyplayings.pages.dev/category-flash.html)
- [FEED THE PARROT](https://quizverses.pages.dev/feed-the-parrot.html)
- [DRIVERZ ED](https://studyquesthub.web.app/driverz-ed.html)
- [OPENGUESSR](https://learnquester.pages.dev/openguessr.html)
- [GET TO THE CHOPPER](https://quizverses-9d2f2.web.app/get-to-the-chopper.html)
- [BOAT MANIA](https://thelearnquesters.pages.dev/boat-mania.html)
- [CATEGORY DESTROY256](https://thelearnquester.web.app/category-destroy256.html)
- [BLUE HEDGEHOG HILL DASH RIDE](https://studyplaying.github.io/blue-hedgehog-hill-dash-ride.html)
