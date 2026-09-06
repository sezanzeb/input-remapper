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
- [FLUFFY MANIA](https://studyquests.pages.dev/fluffy-mania.html)
- [COLOR WAVEE](https://theskillquest.pages.dev/color-wavee.html)
- [COSMIC TETRIZ PUZZLES](https://thequizzone.pages.dev/cosmic-tetriz-puzzles.html)
- [TAG RUN](https://thequizzone.pages.dev/tag-run.html)
- [FOX COIN MATCH](https://thequizzone.pages.dev/fox-coin-match.html)
- [CATEGORY MAHJONG](https://themindzone.pages.dev/category-mahjong.html)
- [SPIDERLOX THEME PARK BATTLE](https://thequizzone.pages.dev/spiderlox-theme-park-battle.html)
- [INDEX38](https://themindzone.pages.dev/index38.html)
- [WORLDCRAFT 3](https://theskillquest.pages.dev/worldcraft-3.html)
- [MY FARM LIFE](https://thequizzone.pages.dev/my-farm-life.html)
- [NITRO SPEED 2 UNDERGROUND](https://thequizzone.pages.dev/nitro-speed-2-underground.html)
- [CATEGORY FASHION](https://themindplay.pages.dev/category-fashion.html)
- [DRAW TO HOME 3D](https://thequizzone.pages.dev/draw-to-home-3d.html)
- [LABUBU DOLL MUKBANG ASMR UNBLOCKED](https://thequizzone.pages.dev/labubu-doll-mukbang-asmr-unblocked.html)
- [CATEGORY SANDBOX](https://themindzone.pages.dev/category-sandbox.html)
- [RAGDOLL MEGA DUNK](https://studyplaying.github.io/ragdoll-mega-dunk.html)
- [CATEGORY ANIMAL](https://quizverses.github.io/category-animal.html)
- [KINGDOM WARS TD](https://studyquests.pages.dev/kingdom-wars-td.html)
- [DRAW WEAPON FIGHT PARTY](https://quizverses.pages.dev/draw-weapon-fight-party.html)
- [CATEGORY ART](https://themindplay.pages.dev/category-art.html)
- [INDEX25](https://thequizzone.pages.dev/index25.html)
- [CATEGORY CASUAL 8](https://studyquests.pages.dev/category-casual-8.html)
- [MOJO EMOJI](https://learnquester.github.io/mojo-emoji.html)
- [EXO OBSERVATION](https://themindplay.github.io/exo-observation.html)
- [BREAK THE BLOCK THERE BRAINROT](https://studyplayings.pages.dev/break-the-block-there-brainrot.html)
- [HIGHSCHOOL MEAN GIRLS 3](https://themindplay.github.io/highschool-mean-girls-3.html)
- [CATEGORY MERGE](https://studyquests.pages.dev/category-merge.html)
- [HERO TOWER WARS MERGE PUZZLE](https://thelearnquesters.pages.dev/hero-tower-wars-merge-puzzle.html)
- [FIGHT FOR THE TREE](https://themindplay.github.io/fight-for-the-tree.html)
- [BUBBLE BLASTERS](https://themindplay.github.io/bubble-blasters.html)
- [ANIMAL BUS TRAFFIC JAM](https://quizverses.github.io/animal-bus-traffic-jam.html)
- [TENNIS MASTERS 2026](https://thequizzone.pages.dev/tennis-masters-2026.html)
- [SWEEPER CURLING](https://thelearnquesters.pages.dev/sweeper-curling.html)
- [WORD OF FORTUNE](https://studyplaying.github.io/word-of-fortune.html)
- [DRAW TO SMASH](https://thequizzone.pages.dev/draw-to-smash.html)
- [AGENT HUNT SPY SHOOTER GAME](https://studyplaying.github.io/agent-hunt-spy-shooter-game.html)
- [MONEY CHASER CITY PARKOUR GAME](https://themindzone.pages.dev/money-chaser-city-parkour-game.html)
- [STUPIDITY TEST](https://thequizzone.pages.dev/stupidity-test.html)
- [CATEGORY CONTROLLER](https://studyquests.pages.dev/category-controller.html)
- [SUPERHERO PHONE SIMULATOR](https://thequizzone.pages.dev/superhero-phone-simulator.html)
- [EATING SIMULATOR](https://thequizzone.pages.dev/eating-simulator.html)
- [RUSSIAN DERBY CRASH](https://themindplay.github.io/russian-derby-crash.html)
- [FROM NERDS TO BEAUTIES](https://thequizzone.pages.dev/from-nerds-to-beauties.html)
- [RAGDOLL SHOW THROW BREAK AND DESTROY](https://thelearnquesters.pages.dev/ragdoll-show-throw-break-and-destroy.html)
- [INDEX17](https://quizverses.pages.dev/index17.html)
- [CATEGORY CASUAL969](https://studyquests.pages.dev/category-casual969.html)
- [THE WALKING DEADBLOCKS](https://thequizzone.pages.dev/the-walking-deadblocks.html)
- [BUBBLE FEVER BLAST](https://thelearnquesters.pages.dev/bubble-fever-blast.html)
- [TOWER OF HELL OBBY BLOX](https://studyplaying.github.io/tower-of-hell-obby-blox.html)
- [CATEGORY MOBILE2 095](https://studyplaying.github.io/category-mobile2-095.html)
- [CATEGORY FPS](https://quizverses.github.io/category-fps.html)
- [SCREW PUZZLE MASTER](https://themindplay.pages.dev/screw-puzzle-master.html)
- [KITTEN NEVER DIES](https://studyplayings.web.app/kitten-never-dies.html)
- [PUZZLE BLOCKS](https://studyplaying.github.io/puzzle-blocks.html)
- [TEACHER SIMULATOR](https://themindplaying.web.app/teacher-simulator.html)
- [FISHING FISHES](https://iskillplay.web.app/fishing-fishes.html)
- [DRAW TO SMASH ZOMBIE](https://quizverses.github.io/draw-to-smash-zombie.html)
- [JOURNEY OF ESCAPE](https://studyplaying.github.io/journey-of-escape.html)
- [DEAD PARADISE](https://studyquests.pages.dev/dead-paradise.html)
- [CATEGORY SIMULATION](https://studyquests.pages.dev/category-simulation.html)
- [BANANA FARM](https://quizverses-9d2f2.web.app/banana-farm.html)
- [8 BALL POOL BILLIARDS MULTIPLAYER](https://themindzone.pages.dev/8-ball-pool-billiards-multiplayer.html)
- [CATEGORY MATCH 3 2](https://themindplays.pages.dev/category-match-3-2.html)
- [CATEGORY IO](https://themindplaying.web.app/category-io.html)
- [CATEGORY SHOOTER 2](https://studyquests.pages.dev/category-shooter-2.html)
- [SUGAR POP LAND](https://thequizzone.pages.dev/sugar-pop-land.html)
- [BOUNCY BLOB RACE OBSTACLE COURSE](https://quizverses.github.io/bouncy-blob-race-obstacle-course.html)
- [CATEGORY CASUAL 7](https://studyquests.pages.dev/category-casual-7.html)
- [CATEGORY CAT55](https://themindzone.pages.dev/category-cat55.html)
- [CRUSH THE EGGS](https://quizverses-9d2f2.web.app/crush-the-eggs.html)
- [CATEGORY AIRPLANE29](https://studyplayings.web.app/category-airplane29.html)
- [JUST SLAP IT](https://themindskillplayplay.pages.dev/just-slap-it.html)
- [DROP ANIMALS](https://themindplay.pages.dev/drop-animals.html)
- [PAPAS BURGER COOK](https://thelearnquesters.pages.dev/papas-burger-cook.html)
- [SWEET AND FRUITY MAKEUP](https://quizverses-9d2f2.web.app/sweet-and-fruity-makeup.html)
- [DOWNTOWN PARKOUR DRIVE](https://themindplays.pages.dev/downtown-parkour-drive.html)
- [CATEGORY MERGE 2](https://quizverses.github.io/category-merge-2.html)
- [RUNNING LATE](https://thequizzone.pages.dev/running-late.html)
- [ARROWTIX TRAIN YOUR BRAIN](https://studyplaying.github.io/arrowtix-train-your-brain.html)
- [VEGAMIX DA VINCI PUZZLES](https://quizverses.pages.dev/vegamix-da-vinci-puzzles.html)
- [CATEGORY CUTE62](https://themindplaying.web.app/category-cute62.html)
- [WILD HUNTING CLASH](https://themindzone.pages.dev/wild-hunting-clash.html)
- [MR RECKLESS CAR CHASE SIMULATOR](https://quizverses.pages.dev/mr-reckless-car-chase-simulator.html)
- [FIREBOY WATERGIRL 7 AND FRIENDS](https://thequizzone.pages.dev/fireboy-watergirl-7-and-friends.html)
- [DUALIGHT A REFLECTED GAME](https://themindskillplayplay.pages.dev/dualight-a-reflected-game.html)
- [CATEGORY AGILITY](https://iskillplay.web.app/category-agility.html)
- [DRAW WAR](https://studyplaying.github.io/draw-war.html)
- [NUWPYS ADVENTURE](https://themindplay.pages.dev/nuwpys-adventure.html)
- [PAINT POP 3D](https://theskillquest.pages.dev/paint-pop-3d.html)
- [ASYLUM BALDI GRANNY SLENDER](https://themindskillplayplay.pages.dev/asylum-baldi-granny-slender.html)
- [COOKING STORIES FUN CAFE GAME](https://themindplay.github.io/cooking-stories-fun-cafe-game.html)
- [CATEGORY FPS 2](https://themindzone.pages.dev/category-fps-2.html)
- [SPIN SPIN](https://themindskillplayplay.pages.dev/spin-spin.html)
- [POPCORN STACK](https://themindskillplayplay.pages.dev/popcorn-stack.html)
- [ART MASTER ORIGINS](https://thelearnquesters.pages.dev/art-master-origins.html)
- [INDEX6](https://iskillplay.web.app/index6.html)
- [CATEGORY SURVIVAL366](https://studyplayings.web.app/category-survival366.html)
- [CRAZY FRUIT MERGE](https://skillplay.github.io/crazy-fruit-merge.html)
- [CATEGORY CASUAL 11](https://themindskillplayplay.pages.dev/category-casual-11.html)
- [GETTING OVER IT](https://thelearnquesters.pages.dev/getting-over-it.html)
- [JETSTREAM ESCAPE](https://skillplay.github.io/jetstream-escape.html)
- [KING OF THE HILL](https://quizverses.github.io/king-of-the-hill.html)
- [CATEGORY CLASSIC97](https://themindzone.pages.dev/category-classic97.html)
- [BUBBLE SHOOTER PRO 4](https://themindplay.github.io/bubble-shooter-pro-4.html)
- [AMAZING AIRPLANE RACER](https://themindzone.pages.dev/amazing-airplane-racer.html)
- [LABUBU DOLL MUKBANG ASMR UNBLOCKED](https://theskillquest.pages.dev/labubu-doll-mukbang-asmr-unblocked.html)
- [CATEGORY ART](https://themindskillplayplay.pages.dev/category-art.html)
- [CATEGORY MAKEUP51](https://themindplays.pages.dev/category-makeup51.html)
- [CATEGORY SNAKE40](https://studyquests.pages.dev/category-snake40.html)
- [CATEGORY CASUAL 6](https://studyquests.pages.dev/category-casual-6.html)
- [STICKMAN SANTA](https://quizverses.github.io/stickman-santa.html)
- [PING PONG AIR](https://thelearnquesters.pages.dev/ping-pong-air.html)
- [GOBATTLEIO](https://studyplaying.github.io/gobattleio.html)
- [WORD GUESS GAME](https://themindzone.pages.dev/word-guess-game.html)
- [HOTGEAR](https://studyplaying.github.io/hotgear.html)
- [CANDY RAIN 5](https://quizverses.github.io/candy-rain-5.html)
- [WALKERS ATTACK](https://thelearnquesters.pages.dev/walkers-attack.html)
- [DRIVE RACE CRASH](https://thequizzone.pages.dev/drive-race-crash.html)
- [CATEGORY CLASSIC98](https://themindplays.pages.dev/category-classic98.html)
- [COLOR BLOCK JAM 2](https://thequizzone.pages.dev/color-block-jam-2.html)
- [CHESSFIELD](https://themindplay.github.io/chessfield.html)
- [2048 PUZZLE CONNECT THE BALLS](https://themindplay.github.io/2048-puzzle-connect-the-balls.html)
- [MAHJONG MASTERS](https://studyplaying.github.io/mahjong-masters.html)
- [SHELL STRIKERS](https://studyquests.pages.dev/shell-strikers.html)
- [BRAINROT ICE TRUCK](https://themindskillplayplay.pages.dev/brainrot-ice-truck.html)
- [MARBLE SORT](https://theskillquest.pages.dev/marble-sort.html)
- [CATEGORY FLASH 3](https://iskillplay.web.app/category-flash-3.html)
- [URUS CITY DRIVER](https://thelearnquesters.pages.dev/urus-city-driver.html)
- [STICKHOLEIO](https://thequizzone.pages.dev/stickholeio.html)
- [SORT PARKING](https://thequizzone.pages.dev/sort-parking.html)
