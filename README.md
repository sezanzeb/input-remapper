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
- [WHEEL OF BINGO](https://thelearnquester.web.app/wheel-of-bingo.html)
- [CATEGORY PREMIUM PERKS74](https://learnquester.pages.dev/category-premium-perks74.html)
- [REAL MOTORBIKE SIMULATOR RACE 3D](https://quizverses-9d2f2.web.app/real-motorbike-simulator-race-3d.html)
- [GOAL IO](https://thelearnquester.web.app/goal-io.html)
- [MERGE BRICK BREAKER](https://thelearnquester.web.app/merge-brick-breaker.html)
- [CATEGORY IDLE445](https://learnquester.github.io/category-idle445.html)
- [ASTRAL ESCAPE](https://studyquesthub.web.app/astral-escape.html)
- [67 CLICKER](https://learnquester.github.io/67-clicker.html)
- [CATEGORY MOBILE2 097](https://quizverses.github.io/category-mobile2-097.html)
- [ASMR WASHING FIXING](https://thelearnquester.web.app/asmr-washing-fixing.html)
- [CATEGORY HERO72](https://thelearnquester.web.app/category-hero72.html)
- [CATEGORY SOLITAIRE27](https://studyquests.github.io/category-solitaire27.html)
- [CATEGORY MATCH 3 GAMES](https://studyquests.github.io/category-match-3-games.html)
- [DYNAMONS 12](https://thelearnquester.web.app/dynamons-12.html)
- [COIN MERGE MACHINE](https://studyquests.github.io/coin-merge-machine.html)
- [CATEGORY IDLE GAMES](https://studyquests.github.io/category-idle-games.html)
- [STICKER JAM PEEL OFF MATCH](https://quizverses-9d2f2.web.app/sticker-jam-peel-off-match.html)
- [INDEX35](https://quizverses.github.io/index35.html)
- [CATEGORY INCREMENTAL388](https://quizverses.github.io/category-incremental388.html)
- [TRICKY SHOTS](https://quizverses.github.io/tricky-shots.html)
- [NINJA BAMBOO ASSASSIN](https://learnquester.github.io/ninja-bamboo-assassin.html)
- [BUBBLE CLASSIC](https://thelearnquester.web.app/bubble-classic.html)
- [INDEX21](https://learnquester.github.io/index21.html)
- [COLOR BLOCK SORT](https://quizverses.github.io/color-block-sort.html)
- [SERIOUS BRO](https://quizverses.github.io/serious-bro.html)
- [VAULT BREAKER](https://learnquester.github.io/vault-breaker.html)
- [STICKMAN ARCHER SHOOTING ARROWS AT REDS](https://studyquests.github.io/stickman-archer-shooting-arrows-at-reds.html)
- [TIMEWARRIORS](https://quizverses.github.io/timewarriors.html)
- [ULTIMATE SPORTS CAR DRIFT](https://studyquests.github.io/ultimate-sports-car-drift.html)
- [LINE ON HOLE](https://thelearnquester.web.app/line-on-hole.html)
- [CATEGORY ADVENTURE 2](https://learnquester.github.io/category-adventure-2.html)
- [CATEGORY CONTROLLER](https://thelearnquester.web.app/category-controller.html)
- [MICKEY RUN ADVENTURE GAME](https://thelearnquester.web.app/mickey-run-adventure-game.html)
- [STICKMAN KOMBAT 2D](https://learnquester.github.io/stickman-kombat-2d.html)
- [CATEGORY SURVIVAL366](https://studyquests.github.io/category-survival366.html)
- [PERFECT SHOT](https://quizverses.github.io/perfect-shot.html)
- [CATEGORY INTERSTELLAR](https://thelearnquester.web.app/category-interstellar.html)
- [LITTLE LILY HALLOWEEN PREP](https://learnquester.github.io/little-lily-halloween-prep.html)
- [TILEMAN IO](https://thelearnquester.web.app/tileman-io.html)
- [FIGHT TRIVIA](https://studyquests.github.io/fight-trivia.html)
- [INDEX5](https://quizverses-9d2f2.web.app/index5.html)
- [DANCE ON HOTSTEPS MOBILE](https://studyquests.github.io/dance-on-hotsteps-mobile.html)
- [CATEGORY MONSTER206](https://quizverses-9d2f2.web.app/category-monster206.html)
- [CATEGORY COLLECT565](https://thelearnquester.web.app/category-collect565.html)
- [CATEGORY STICKMAN175](https://studyquests.github.io/category-stickman175.html)
- [CATEGORY SOCCER](https://studyquests.github.io/category-soccer.html)
- [CATEGORY MOUSE1 699](https://studyquests.github.io/category-mouse1-699.html)
- [CATEGORY RACING DRIVING](https://quizverses-9d2f2.web.app/category-racing-driving.html)
- [GRUKKLE ONSLAUGHT](https://studyquests.github.io/grukkle-onslaught.html)
- [PET FALL](https://learnquester.github.io/pet-fall.html)
- [CATEGORY SURVIVAL](https://studyquests.github.io/category-survival.html)
- [SANDBOX ISLAND WAR](https://quizverses.github.io/sandbox-island-war.html)
- [FIND THE GHOST CAT](https://learnquester.github.io/find-the-ghost-cat.html)
- [CATEGORY COOKING46](https://learnquester.github.io/category-cooking46.html)
- [CATEGORY MOUSE1 707](https://studyquests.github.io/category-mouse1-707.html)
- [STICKMAN ZOMBIE VS STICKMAN HERO](https://thelearnquester.web.app/stickman-zombie-vs-stickman-hero.html)
- [CATEGORY BIKE](https://learnquester.github.io/category-bike.html)
- [SUMMER CONNECT](https://quizverses.github.io/summer-connect.html)
- [DYNAMONS 11](https://learnquester.github.io/dynamons-11.html)
- [FOOTBALL PENALTY 2026](https://studyquests.github.io/football-penalty-2026.html)
- [BRAIN TEST IQ CHALLENGE 2](https://thelearnquester.web.app/brain-test-iq-challenge-2.html)
- [CATEGORY BASKETBALL](https://learnquester.github.io/category-basketball.html)
- [SAMURAI MADNESS](https://learnquester.github.io/samurai-madness.html)
- [TONY ARCHER](https://learnquester.github.io/tony-archer.html)
- [INDEX4](https://quizverses.github.io/index4.html)
- [CATEGORY COOKING](https://thelearnquester.web.app/category-cooking.html)
- [CHICKEN BANANA RUN](https://learnquester.github.io/chicken-banana-run.html)
- [CATEGORY CONNECT68](https://learnquester.github.io/category-connect68.html)
- [CUTE SHEEP SKYBLOCK](https://thelearnquester.web.app/cute-sheep-skyblock.html)
- [CATEGORY MATCH 3 2](https://quizverses.github.io/category-match-3-2.html)
- [CHEERFUL PLUMBER](https://studyquests.github.io/cheerful-plumber.html)
- [CATEGORY MERGE224](https://studyplayings.pages.dev/category-merge224.html)
- [CATEGORY FPS](https://quizverses-9d2f2.web.app/category-fps.html)
- [FIND GOODS](https://quizverses.github.io/find-goods.html)
- [CATEGORY JIGSAW](https://quizverses.github.io/category-jigsaw.html)
- [CATEGORY FOOTBALL](https://quizverses-9d2f2.web.app/category-football.html)
- [ONLINE PORTAL](https://brainquests.onrender.com/)
- [PIXEL NUMBER DIY COLORING](https://studyplayings.web.app/pixel-number-diy-coloring.html)
- [MOSCOW METRO DRIVER 3D](https://studyquests.github.io/moscow-metro-driver-3d.html)
- [CATEGORY PUZZLE 3](https://studyquests.github.io/category-puzzle-3.html)
- [CATEGORY RACING DRIVING 2](https://quizverses.github.io/category-racing-driving-2.html)
- [ORGANIZER MASTER](https://quizverses.pages.dev/organizer-master.html)
- [DIGITAL CIRCUS IO](https://studyplayings.web.app/digital-circus-io.html)
- [MAGIC FINGER PUZZLE 3D](https://studyquests.github.io/magic-finger-puzzle-3d.html)
- [CUTE CATS ADVENTURES](https://quizverses.github.io/cute-cats-adventures.html)
- [CATEGORY CARTOON](https://studyquests.github.io/category-cartoon.html)
- [RICH CHOICE RUN](https://quizverses.github.io/rich-choice-run.html)
- [BLOCK CRAFT 3D](https://studyplayings.pages.dev/block-craft-3d.html)
- [CATEGORY FREE](https://quizverses-9d2f2.web.app/category-free.html)
- [SORT TILES](https://quizverses.github.io/sort-tiles.html)
- [MATCHING PUZZLE](https://thelearnquester.web.app/matching-puzzle.html)
- [CATEGORY SOCCER](https://studyplayings.pages.dev/category-soccer.html)
- [CATEGORY WAR137](https://studyplayings.pages.dev/category-war137.html)
- [HEROIC KNIGHT](https://quizverses.pages.dev/heroic-knight.html)
- [MANSION STORY MATCH](https://studyquests.github.io/mansion-story-match.html)
- [AUTUMN GLAM GALA](https://studyplayings.web.app/autumn-glam-gala.html)
- [MATCH 3 DREAM ROOM](https://studyplayings.web.app/match-3-dream-room.html)
- [CAR PARKING MASTER 3D REAL DRIVING SIMULATOR](https://quizverses.pages.dev/car-parking-master-3d-real-driving-simulator.html)
- [AVATAR MASTER FIX UP FACE](https://studyplayings.web.app/avatar-master-fix-up-face.html)
- [CATEGORY RPG80](https://quizverses-9d2f2.web.app/category-rpg80.html)
- [CATEGORY PUZZLE 4](https://thelearnquester.web.app/category-puzzle-4.html)
- [DELIVERY NOW](https://studyquests.github.io/delivery-now.html)
- [CATEGORY AVOID](https://studyquests.github.io/category-avoid.html)
- [CATEGORY STRATEGY 2](https://studyquests.github.io/category-strategy-2.html)
- [OBBY SURVIVE PARKOUR](https://studyplayings.web.app/obby-survive-parkour.html)
- [COOKING RESTAURANT KITCHEN](https://quizverses.pages.dev/cooking-restaurant-kitchen.html)
- [ONET MONSTER BOOK](https://quizverses.pages.dev/onet-monster-book.html)
- [MERGE RACER STUNTS CAR](https://studyplaying.github.io/merge-racer-stunts-car.html)
- [KITTEN NEVER DIES](https://studyplayings.web.app/kitten-never-dies.html)
- [MILITARY CUBES 2048](https://studyplaying.github.io/military-cubes-2048.html)
- [CARJAMCOLOR](https://quizverses.github.io/carjamcolor.html)
- [MATCH ARENA](https://quizverses.pages.dev/match-arena.html)
- [PET CONNECT MATCH](https://learnquester.github.io/pet-connect-match.html)
- [CHESS DUEL](https://studyplaying.github.io/chess-duel.html)
- [NOOB FUN FISHING](https://studyplayings.web.app/noob-fun-fishing.html)
- [HEAD JUMP](https://studyquests.github.io/head-jump.html)
- [PARKING FURY 3D NIGHT CITY](https://studyplayings.pages.dev/parking-fury-3d-night-city.html)
- [CATEGORY COLLECT565](https://quizverses-9d2f2.web.app/category-collect565.html)
- [WOOD HEXA FACTORY](https://studyquests.github.io/wood-hexa-factory.html)
- [MAHJONG SLIDE PUZZLE](https://quizverses.github.io/mahjong-slide-puzzle.html)
- [CATEGORY BLOCK94](https://studyquesthub.web.app/category-block94.html)
- [CATEGORY WEBGAME](https://studyquests.github.io/category-webgame.html)
- [STUDENT AND TEACHER](https://studyplayings.web.app/student-and-teacher.html)
- [NUTS BOLTS WOOD PUZZLE GAME](https://studyplayings.web.app/nuts-bolts-wood-puzzle-game.html)
- [SPEEDRUN PLATFORMER](https://thelearnquesters.pages.dev/speedrun-platformer.html)
- [COLOR BLOCK JAM](https://thequizzone.pages.dev/color-block-jam.html)
- [CATEGORY LOGIC538](https://quizverses-9d2f2.web.app/category-logic538.html)
- [RUN 3D](https://studyplaying.github.io/run-3d.html)
- [FLOWBALL](https://studyplaying.github.io/flowball.html)
- [CATEGORY AGILITY](https://themindzone.pages.dev/category-agility.html)
