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
- [REAL RACING 3D](https://iskillquest.pages.dev/real-racing-3d.html)
- [URBAN ASSAULT FORCE](https://learnquester.github.io/urban-assault-force.html)
- [DREAM RESTAURANT 3D](https://studyquests.pages.dev/dream-restaurant-3d.html)
- [PASSENGER SORT](https://studyquests.pages.dev/passenger-sort.html)
- [PANDA SHOP SIMULATOR](https://studyquests.pages.dev/panda-shop-simulator.html)
- [FALLING ART RAGDOLL SIMULATOR](https://learnquester.github.io/falling-art-ragdoll-simulator.html)
- [AIRPORT MASTER PLANE TYCOON](https://learnquester.github.io/airport-master-plane-tycoon.html)
- [JUMP UP 3D BASKETBALL GAME](https://learnquester.github.io/jump-up-3d-basketball-game.html)
- [FLAPPY RUSH](https://studyplayings.pages.dev/flappy-rush.html)
- [CATEGORY BASKETBALL 2](https://learnquester.github.io/category-basketball-2.html)
- [KNOCKOUT DUDES](https://studyplayings.pages.dev/knockout-dudes.html)
- [COZY KITCHEN MERGE](https://learnquester.github.io/cozy-kitchen-merge.html)
- [MATCH MASTER](https://studyplaying.github.io/match-master.html)
- [CUT THE ROPE TIME TRAVEL](https://learnquester.github.io/cut-the-rope-time-travel.html)
- [BOMBER BATTLE ARENA](https://studyplaying.github.io/bomber-battle-arena.html)
- [CATEGORY RPG](https://studyplaying.github.io/category-rpg.html)
- [HALLOWEEN FRUIT SLICE](https://studyplaying.github.io/halloween-fruit-slice.html)
- [CATEGORY INTERSTELLARNETWORK](https://learnquester.github.io/category-interstellarnetwork.html)
- [COLOR MIX JELLY MERGE](https://studyplaying.github.io/color-mix-jelly-merge.html)
- [ZOO SHAP](https://studyplaying.github.io/zoo-shap.html)
- [ARCADE ROPE](https://studyplayings.pages.dev/arcade-rope.html)
- [GEOMETRY OPEN WORLD](https://studyplaying.github.io/geometry-open-world.html)
- [CATEGORY STRATEGY 2](https://studyplaying.github.io/category-strategy-2.html)
- [MY ARCADE CENTER](https://studyplaying.github.io/my-arcade-center.html)
- [OBBY TOWER PARKOUR CLIMB](https://studyplaying.github.io/obby-tower-parkour-climb.html)
- [SPOTDIFFERS](https://studyplayings.pages.dev/spotdiffers.html)
- [CATEGORY SANDBOX40](https://learnquester.github.io/category-sandbox40.html)
- [CATEGORY MINECRAFT81](https://studyplayings.pages.dev/category-minecraft81.html)
- [CATEGORY CAN T STOP PLAYING212](https://studyplayings.pages.dev/category-can-t-stop-playing212.html)
- [LINK FLOW](https://learnquester.github.io/link-flow.html)
- [MEOW SLIDE](https://learnquester.github.io/meow-slide.html)
- [CATEGORY SPACE57](https://studyplaying.github.io/category-space57.html)
- [HERO RABBIT IDLE SURVIVOR RPG](https://studyplaying.github.io/hero-rabbit-idle-survivor-rpg.html)
- [CATEGORY WATER39](https://studyplaying.github.io/category-water39.html)
- [CATEGORY 2D1 060](https://studyplayings.pages.dev/category-2d1-060.html)
- [BUBBLE SHOOTER PANDA BLAST](https://studyplaying.github.io/bubble-shooter-panda-blast.html)
- [INDEX14](https://learnquester.github.io/index14.html)
- [BLOCKS BREAKER](https://learnquester.github.io/blocks-breaker.html)
- [CATEGORY SHOOTER](https://learnquester.github.io/category-shooter.html)
- [SPIDER EVOLUTION](https://studyplayings.web.app/spider-evolution.html)
- [SOLITAIRE FARM SEASONS 3](https://studyplayings.pages.dev/solitaire-farm-seasons-3.html)
- [GEOMETRY ARROW 2](https://learnquester.github.io/geometry-arrow-2.html)
- [FOOD TOWER DEFENSE](https://learnquester.github.io/food-tower-defense.html)
- [CAR SERVICE TYCOON](https://studyplayings.pages.dev/car-service-tycoon.html)
- [SHEEP SHEEP DUCK](https://studyplayings.pages.dev/sheep-sheep-duck.html)
- [CATEGORY CRASH32](https://studyplayings.pages.dev/category-crash32.html)
- [EMOJI DROP THEMES](https://learnquester.github.io/emoji-drop-themes.html)
- [STEAL ITEMS IO](https://studyplayings.pages.dev/steal-items-io.html)
- [FREE THE BALL](https://studyplaying.github.io/free-the-ball.html)
- [CUTE CRAFT LAB](https://studyplaying.github.io/cute-craft-lab.html)
- [FRIDAY NIGHT SPRUNKI](https://studyplayings.pages.dev/friday-night-sprunki.html)
- [TAIL GUN CHARLIE](https://studyplaying.github.io/tail-gun-charlie.html)
- [CATEGORY PUZZLE](https://studyplayings.pages.dev/category-puzzle.html)
- [GEAR WARS](https://studyplayings.pages.dev/gear-wars.html)
- [TAP TO COLOR PAINTING BOOK](https://studyplaying.github.io/tap-to-color-painting-book.html)
- [BOXTERIA](https://studyplaying.github.io/boxteria.html)
- [CLASSIC LABYRINTH 3D MAZE](https://studyplaying.github.io/classic-labyrinth-3d-maze.html)
- [MATCHING PUZZLE](https://studyplaying.github.io/matching-puzzle.html)
- [ARCHERY MASTER BOW AND ARROW](https://studyplaying.github.io/archery-master-bow-and-arrow.html)
- [CATEGORY FPS](https://learnquester.github.io/category-fps.html)
- [SEA MONSTERS MAHJONG](https://studyplaying.github.io/sea-monsters-mahjong.html)
- [JETSTREAM ESCAPE](https://learnquester.github.io/jetstream-escape.html)
- [RAGDOLL PARKOUR SIMULATOR](https://learnquester.github.io/ragdoll-parkour-simulator.html)
- [FACE CHANGES](https://studyplaying.github.io/face-changes.html)
- [SUPERMARKET SIMULATOR DREAM STORE](https://studyplaying.github.io/supermarket-simulator-dream-store.html)
- [FEED ME MONSTERS IDLE BATTLE](https://studyplayings.pages.dev/feed-me-monsters-idle-battle.html)
- [KINGS AND QUEENS MAHJONG](https://studyplayings.pages.dev/kings-and-queens-mahjong.html)
- [MARBLE PUZZLE QUEST](https://learnquester.github.io/marble-puzzle-quest.html)
- [OBBY CHAMPIONS](https://learnquester.github.io/obby-champions.html)
- [DRAW BRIDGE PUZZLE](https://studyplaying.github.io/draw-bridge-puzzle.html)
- [GRANDMAS LAST STAND](https://learnquester.github.io/grandmas-last-stand.html)
- [MERGE PLANETS](https://studyplayings.pages.dev/merge-planets.html)
- [GOKARTS IO](https://studyplayings.pages.dev/gokarts-io.html)
- [ABOUT A FROG](https://studyplaying.github.io/about-a-frog.html)
- [ALIEN INTELLIGENCE TEST](https://learnquester.github.io/alien-intelligence-test.html)
- [FEET DOCTOR URGENCY CARE](https://learnquester.github.io/feet-doctor-urgency-care.html)
- [FARMER RUSH IDLE FARM GAME](https://studyplaying.github.io/farmer-rush-idle-farm-game.html)
- [RAGDOLL ARENA 2 PLAYER](https://studyplayings.pages.dev/ragdoll-arena-2-player.html)
- [SNIPER SHOT SECRET MISSION](https://studyplaying.github.io/sniper-shot-secret-mission.html)
- [ASMR MAKEOVER MAKEUP STUDIO](https://studyplayings.pages.dev/asmr-makeover-makeup-studio.html)
- [DALGONA GAME2](https://studyplaying.github.io/dalgona-game2.html)
- [GODS MIXER](https://studyplaying.github.io/gods-mixer.html)
- [HAPPY FARM THE CROP](https://quizverses-9d2f2.web.app/happy-farm-the-crop.html)
- [DEAD FACES CLONE ONLINE](https://studyquests.github.io/dead-faces-clone-online.html)
- [FOXY ECO SORT](https://studyplaying.github.io/foxy-eco-sort.html)
- [SHIP CONTROL 3D](https://studyquesthub.web.app/ship-control-3d.html)
- [BARBEE SUMMER VACATION](https://learnquester.github.io/barbee-summer-vacation.html)
- [ARCADE ROPE](https://studyquests.github.io/arcade-rope.html)
- [AIRPORT CONTROLLER](https://studyquesthub.web.app/airport-controller.html)
- [WORLD FLAGS TRIVIA](https://studyquesthub.web.app/world-flags-trivia.html)
- [HOOK MASTER MAFIA CITY](https://quizverses.pages.dev/hook-master-mafia-city.html)
- [CATEGORY HUB](https://studyplayings.pages.dev/category-hub.html)
- [CATEGORY UNBLOCKED](https://studyquests.github.io/category-unblocked.html)
- [BLOCK BLAST 2048](https://studyplaying.github.io/block-blast-2048.html)
- [MEGA RAMP CAR STUNTS](https://studyplayings.pages.dev/mega-ramp-car-stunts.html)
- [HEXA TILE TRIO](https://studyquests.github.io/hexa-tile-trio.html)
- [FILL THE BOTTLE](https://studyplayings.pages.dev/fill-the-bottle.html)
- [THUMBPINBALL](https://studyplayings.pages.dev/thumbpinball.html)
- [GOODELUXE](https://studyquests.github.io/goodeluxe.html)
- [UNLOCK THE BOLTS](https://studyplaying.github.io/unlock-the-bolts.html)
- [MINI GAMES RELAX COLLECTION 2](https://studyplaying.github.io/mini-games-relax-collection-2.html)
- [COMBINE PICKAXES](https://studyquests.pages.dev/combine-pickaxes.html)
- [FUSION 2048](https://quizverses.pages.dev/fusion-2048.html)
- [ACOX RUNNER](https://quizverses.pages.dev/acox-runner.html)
- [OFFICE GOLF](https://studyquests.github.io/office-golf.html)
- [SAVE MY HERO](https://studyplaying.github.io/save-my-hero.html)
- [CATEGORY BATTLE 2](https://studyquesthub.web.app/category-battle-2.html)
- [ZUMBIA QUEST](https://studyquesthub.web.app/zumbia-quest.html)
- [BUS DRIVER SIMULATOR 3D](https://studyquests.github.io/bus-driver-simulator-3d.html)
- [THE WHITE ROOM 4](https://studyquests.github.io/the-white-room-4.html)
- [SOLITAIRE TAIL](https://learnquester.github.io/solitaire-tail.html)
- [THATS MY SEAT LOGIC PUZZLE](https://studyquests.github.io/thats-my-seat-logic-puzzle.html)
- [OBBY DUMB OR GENIUS IQ TEST](https://quizverses.pages.dev/obby-dumb-or-genius-iq-test.html)
- [CATEGORY CARE](https://studyplayings.pages.dev/category-care.html)
- [CATEGORY RUNNING](https://studyplayings.pages.dev/category-running.html)
- [MY FARM LIFE](https://learnquester.github.io/my-farm-life.html)
- [BLOCK PUZZLE CATS](https://studyquests.github.io/block-puzzle-cats.html)
- [CATEGORY ARENA255](https://studyquests.github.io/category-arena255.html)
- [BARBEE MET GALA TRANSFORMATION](https://studyplaying.github.io/barbee-met-gala-transformation.html)
- [INDEX4](https://studyplayings.pages.dev/index4.html)
- [EXIT PUZZLE](https://studyplaying.github.io/exit-puzzle.html)
- [QUIZ SQUID ROUND](https://studyquests.github.io/quiz-squid-round.html)
- [ARROW CUBE ESCAPE](https://learnquester.github.io/arrow-cube-escape.html)
- [CATEGORY MEDIEVAL15](https://studyquests.github.io/category-medieval15.html)
- [SCHOOLBOY RUNAWAY ROOM ESCAPE](https://quizverses.pages.dev/schoolboy-runaway-room-escape.html)
- [CATEGORY CASUAL 10](https://studyquests.github.io/category-casual-10.html)
- [LABUBA HALLOWEEN INFESTATION](https://studyplaying.github.io/labuba-halloween-infestation.html)
- [HOOP RIVALS](https://quizverses.pages.dev/hoop-rivals.html)
- [BOOM LAND LITE](https://studyquests.pages.dev/boom-land-lite.html)
- [EMOJI SMASHER SMILEY GAME](https://learnquester.github.io/emoji-smasher-smiley-game.html)
