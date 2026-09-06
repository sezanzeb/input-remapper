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
- [CATEGORY PIXEL313](https://thelearnquesters.pages.dev/category-pixel313.html)
- [CATEGORY THINKY](https://studyquests.github.io/category-thinky.html)
- [ANOMALY CONTENT RECORD](https://quizverses.github.io/anomaly-content-record.html)
- [HEXA TILE TRIO](https://studyquests.github.io/hexa-tile-trio.html)
- [CATEGORY AVOID295](https://quizverses-9d2f2.web.app/category-avoid295.html)
- [GUESS THE DRAWING](https://quizverses-9d2f2.web.app/guess-the-drawing.html)
- [ZINDEX](https://studyquests.github.io/zindex.html)
- [HAPPY MONSTERS 2](https://studyplayings.pages.dev/happy-monsters-2.html)
- [MAGECLASH IO](https://studyquests.github.io/mageclash-io.html)
- [CATEGORY ANIMAL216](https://studyplayings.web.app/category-animal216.html)
- [CATEGORY PUZZLE 8](https://studyplaying.github.io/category-puzzle-8.html)
- [ARCHERS RANDOM](https://quizverses-9d2f2.web.app/archers-random.html)
- [SQUIDGAMEIO](https://learnquester.github.io/squidgameio.html)
- [BACKROOMS SKIBIDI TERRORS](https://quizverses.github.io/backrooms-skibidi-terrors.html)
- [PLUG MAN RACE](https://studyquests.github.io/plug-man-race.html)
- [NAUTILUS SPACESHIP ESCAPE](https://studyplaying.github.io/nautilus-spaceship-escape.html)
- [100 DOORS CHALLENGE](https://quizverses.github.io/100-doors-challenge.html)
- [STREET BALL JAM](https://studyquests.github.io/street-ball-jam.html)
- [CATEGORY CASUAL](https://studyplaying.github.io/category-casual.html)
- [CATEGORY JUMPING150](https://studyplayings.web.app/category-jumping150.html)
- [ELLIE AND BEN CHRISTMAS EVE](https://studyplayings.web.app/ellie-and-ben-christmas-eve.html)
- [MAGIC KINGDOM HEX MATCH](https://studyquests.github.io/magic-kingdom-hex-match.html)
- [FASHION WORLD SIMULATOR](https://quizverses.github.io/fashion-world-simulator.html)
- [SNAP FIX](https://studyquests.github.io/snap-fix.html)
- [HIGH HEELS 2](https://studyquesthub.web.app/high-heels-2.html)
- [BOBBLEHEAD BALL](https://studyquests.github.io/bobblehead-ball.html)
- [PET ME MAZE](https://quizverses.github.io/pet-me-maze.html)
- [CATEGORY OBBY56](https://quizverses-9d2f2.web.app/category-obby56.html)
- [MEDIEVAL ESCAPE](https://studyplayings.web.app/medieval-escape.html)
- [QUIZ SQUID ROUND](https://quizverses-9d2f2.web.app/quiz-squid-round.html)
- [LINK COLOR PICTURES](https://quizverses-9d2f2.web.app/link-color-pictures.html)
- [PUSH THEM](https://studyplayings.web.app/push-them.html)
- [WOODOKU BLOCK PUZZLE](https://studyquests.github.io/woodoku-block-puzzle.html)
- [CATEGORY FPS](https://studyquests.github.io/category-fps.html)
- [BUBBLE SHOOTER TEMPLE JEWELS](https://quizverses.github.io/bubble-shooter-temple-jewels.html)
- [DEADFLIP FRENZY](https://studyplaying.github.io/deadflip-frenzy.html)
- [ROBBY THE LAVA TSUNAMI](https://studyplayings.pages.dev/robby-the-lava-tsunami.html)
- [GAS STATION JUNKYARD TYCOON](https://studyplaying.github.io/gas-station-junkyard-tycoon.html)
- [ENERGY SUPERMAN 3D](https://learnquester.github.io/energy-superman-3d.html)
- [2248 MUSICAL](https://quizverses.github.io/2248-musical.html)
- [UNSCREW THEM ALL](https://studyplayings.web.app/unscrew-them-all.html)
- [CATEGORY FOOTBALL](https://studyplaying.github.io/category-football.html)
- [CATEGORY CUTE](https://thelearnquester.web.app/category-cute.html)
- [FISH RAIN 2](https://studyplaying.github.io/fish-rain-2.html)
- [2048 SORT FACTORY](https://quizverses.github.io/2048-sort-factory.html)
- [BULL RUNNER](https://studyquests.github.io/bull-runner.html)
- [OBBY GYM SIMULATOR ESCAPE](https://learnquester.github.io/obby-gym-simulator-escape.html)
- [CATEGORY MOBILE2 112](https://learnquester.github.io/category-mobile2-112.html)
- [CATEGORY WATER39](https://studyplayings.web.app/category-water39.html)
- [CATEGORY AGILITY 2](https://learnquester.github.io/category-agility-2.html)
- [DRIVE TO SURVIVE](https://studyquests.github.io/drive-to-survive.html)
- [SITEMAP](https://quizverses.pages.dev/sitemap.html)
- [GRANNY GTA VEGAS](https://studyquests.pages.dev/granny-gta-vegas.html)
- [HEXA SORT TRICK OR TREAT](https://studyquesthub.web.app/hexa-sort-trick-or-treat.html)
- [ISLAND BATTLE 3D](https://studyquesthub.web.app/island-battle-3d.html)
- [WHEEL OF BINGO](https://studyplayings.web.app/wheel-of-bingo.html)
- [ATHENA MATCH](https://studyquests.github.io/athena-match.html)
- [CLEAN HOUSE CLEARING TRASH AND DIRT](https://quizverses.github.io/clean-house-clearing-trash-and-dirt.html)
- [DRAW A PATH TO THE FINISH LINE](https://studyquesthub.web.app/draw-a-path-to-the-finish-line.html)
- [EPIC CAR STUNT RACE OBBY](https://studyquests.github.io/epic-car-stunt-race-obby.html)
- [SORCERER MAHJONG MARVELS](https://studyquesthub.web.app/sorcerer-mahjong-marvels.html)
- [WACKY STRIKE](https://studyplaying.github.io/wacky-strike.html)
- [LOVIE CHICS COACHELLA FESTIVAL](https://studyquests.github.io/lovie-chics-coachella-festival.html)
- [CATEGORY WEB PROXY](https://quizverses.pages.dev/category-web-proxy.html)
- [CATEGORY MOBILE2 112](https://quizverses.pages.dev/category-mobile2-112.html)
- [SLIDE RABBIT](https://studyquests.github.io/slide-rabbit.html)
- [SPACE SHOOTER SPEED TYPING CHALLENGE](https://studyplaying.github.io/space-shooter-speed-typing-challenge.html)
- [CATEGORY PIXEL313](https://quizverses.pages.dev/category-pixel313.html)
- [HEXA STACK](https://studyquests.github.io/hexa-stack.html)
- [CATEGORY DRESS UP](https://studyquests.github.io/category-dress-up.html)
- [FRUIT JAM MERGE PUZZLE GAME](https://studyquests.github.io/fruit-jam-merge-puzzle-game.html)
- [CHRISTMAS FIND THE DIFFERENCES](https://studyplayings.pages.dev/christmas-find-the-differences.html)
- [KINGS AND QUEENS MAHJONG](https://studyplayings.pages.dev/kings-and-queens-mahjong.html)
- [STEAL BRAINROT ORIGINAL 3D](https://quizverses.github.io/steal-brainrot-original-3d.html)
- [WOOP CRAWL UP](https://studyquesthub.web.app/woop-crawl-up.html)
- [DIRTY MONEY THE RICH GET RICH](https://quizverses.github.io/dirty-money-the-rich-get-rich.html)
- [ZOMBCOPTER](https://studyquests.github.io/zombcopter.html)
- [CATEGORY COLLECT565](https://studyquests.github.io/category-collect565.html)
- [CATEGORY DEFENSE176](https://studyquests.github.io/category-defense176.html)
- [SPIN THRU](https://studyplaying.github.io/spin-thru.html)
- [BACKGAMMON DUEL](https://studyplayings.web.app/backgammon-duel.html)
- [MIGHTY RUN](https://studyplayings.web.app/mighty-run.html)
- [CATEGORY GUN238](https://studyquesthub.web.app/category-gun238.html)
- [KABOOM MINER](https://quizverses-9d2f2.web.app/kaboom-miner.html)
- [3D BASKETBALLIO DUNK SPORT](https://studyquesthub.web.app/3d-basketballio-dunk-sport.html)
- [INDEX4](https://studyquesthub.web.app/index4.html)
- [TRICKY ARROW 2](https://studyplayings.pages.dev/tricky-arrow-2.html)
- [CATEGORY TETRIS36](https://quizverses.pages.dev/category-tetris36.html)
- [GET TO THE CHOPPER](https://studyquests.github.io/get-to-the-chopper.html)
- [CATEGORY INCREMENTAL](https://thelearnquester.web.app/category-incremental.html)
- [CATEGORY JUMP SCARE21](https://studyplaying.github.io/category-jump-scare21.html)
- [SWORDSMAN ADVENTURE](https://quizverses-9d2f2.web.app/swordsman-adventure.html)
- [KAWAII FRIENDS TILES MATCHER](https://studyquesthub.web.app/kawaii-friends-tiles-matcher.html)
- [SCARY TEACHER 3D RETURNS](https://quizverses.github.io/scary-teacher-3d-returns.html)
- [ROBLOX CRAFT RUN](https://studyquests.github.io/roblox-craft-run.html)
- [CYBER ROLLING GOING BALL 3D](https://studyquests.pages.dev/cyber-rolling-going-ball-3d.html)
- [CATEGORY ROGUELIKE38](https://learnquester.github.io/category-roguelike38.html)
- [COLOR 3D BUMP IT UP](https://quizverses.github.io/color-3d-bump-it-up.html)
- [INDEX7](https://quizverses-9d2f2.web.app/index7.html)
- [CATEGORY IDLE445](https://quizverses.pages.dev/category-idle445.html)
- [IDLE GAME PRISON LIFE](https://studyquests.github.io/idle-game-prison-life.html)
- [SPIN THRU](https://studyquesthub.web.app/spin-thru.html)
- [HYPER NURSE HOSPITAL GAMES](https://quizverses.github.io/hyper-nurse-hospital-games.html)
- [MEGA JUMP](https://quizverses.github.io/mega-jump.html)
- [CATEGORY BUBBLE SHOOTER](https://quizverses.pages.dev/category-bubble-shooter.html)
- [IDLE TOWN BILLIONAIRE](https://studyquests.github.io/idle-town-billionaire.html)
- [CATEGORY FOOD95](https://studyquesthub.web.app/category-food95.html)
- [WORD SEARCH UNIVERSE ANIMALS](https://quizverses.github.io/word-search-universe-animals.html)
- [CANDY MONSTER RAFFI](https://quizverses-9d2f2.web.app/candy-monster-raffi.html)
- [DINO SLIDE](https://quizverses-9d2f2.web.app/dino-slide.html)
- [KINGDOM OF PIXELS](https://quizverses.github.io/kingdom-of-pixels.html)
- [OFFROAD ISLAND](https://studyplayings.web.app/offroad-island.html)
- [BADLAND](https://studyquests.github.io/badland.html)
- [HILL CLIMBING MANIA](https://learnquester.github.io/hill-climbing-mania.html)
- [CATEGORY DESTROY254](https://studyquesthub.web.app/category-destroy254.html)
- [CATCH THE GOOSE](https://studyquesthub.web.app/catch-the-goose.html)
- [VARIETY MECHA](https://studyquesthub.web.app/variety-mecha.html)
- [LOL FUNNY DANCE](https://learnquester.github.io/lol-funny-dance.html)
- [RACE TIME](https://learnquester.github.io/race-time.html)
- [SQUISHY TABA PAW ASMR](https://studyplayings.web.app/squishy-taba-paw-asmr.html)
- [MERGE FLOW](https://quizverses.github.io/merge-flow.html)
- [CRAZY BUNNIES](https://studyquests.github.io/crazy-bunnies.html)
- [IMPOSTER 3D](https://quizverses.github.io/imposter-3d.html)
- [AVATAR MASTER FIX UP FACE](https://studyquests.github.io/avatar-master-fix-up-face.html)
- [WAR STATE IO CONQUER BATTLES](https://learnquester.github.io/war-state-io-conquer-battles.html)
- [SNIPER SHOT SECRET MISSION](https://studyplaying.github.io/sniper-shot-secret-mission.html)
- [TOCA AVATAR MY HOSPITAL](https://studyquesthub.web.app/toca-avatar-my-hospital.html)
- [MARSHMALLOW RUSH](https://studyplaying.github.io/marshmallow-rush.html)
- [FESTIVAL VIBES MAKEUP](https://studyplaying.github.io/festival-vibes-makeup.html)
- [FROGGY HOP](https://studyquests.github.io/froggy-hop.html)
