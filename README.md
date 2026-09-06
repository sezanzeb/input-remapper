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
- [MANYUNYA SAVING THE PRINCESS](https://theskillquest.pages.dev/manyunya-saving-the-princess.html)
- [QUBE 2048 ELF](https://theskillquest.pages.dev/qube-2048-elf.html)
- [ITALIAN BRAINROT CLICKER](https://theskillquest.pages.dev/italian-brainrot-clicker.html)
- [CATEGORY RELAXING223](https://theskillquest.pages.dev/category-relaxing223.html)
- [CATEGORY COLOR195](https://theskillquest.pages.dev/category-color195.html)
- [CATEGORY MERGE 2](https://theskillquest.pages.dev/category-merge-2.html)
- [CATEGORY 3KH0](https://theskillquest.pages.dev/category-3kh0.html)
- [CATEGORY MOUSE1 697](https://theskillquest.pages.dev/category-mouse1-697.html)
- [BATTLER](https://themindzone.pages.dev/battler.html)
- [TIE DYE EXPLOSION OF COLOR](https://themindzone.pages.dev/tie-dye-explosion-of-color.html)
- [CATEGORY POOL 2](https://themindzone.pages.dev/category-pool-2.html)
- [DYNAMONS 7](https://themindzone.pages.dev/dynamons-7.html)
- [CATEGORY OBSTACLE299](https://theskillquest.pages.dev/category-obstacle299.html)
- [BRAINROT MEMORY](https://themindzone.pages.dev/brainrot-memory.html)
- [MONSTER GIRLS BACK TO SCHOOL](https://themindzone.pages.dev/monster-girls-back-to-school.html)
- [PALKOVIL THE WAY HOME](https://themindzone.pages.dev/palkovil-the-way-home.html)
- [CATEGORY 3D1 371](https://theskillquest.pages.dev/category-3d1-371.html)
- [NUMBER TUBES](https://themindzone.pages.dev/number-tubes.html)
- [CATEGORY TOP DOWN251](https://themindzone.pages.dev/category-top-down251.html)
- [CATEGORY ANIMAL216](https://theskillquest.pages.dev/category-animal216.html)
- [WORD GUESS GAME](https://themindzone.pages.dev/word-guess-game.html)
- [HIDDEN OBJECTS ISLAND](https://themindzone.pages.dev/hidden-objects-island.html)
- [CATEGORY MINECRAFT81](https://theskillquest.pages.dev/category-minecraft81.html)
- [SOCCER DASH](https://themindzone.pages.dev/soccer-dash.html)
- [IDLE SUPERMARKET TYCOON](https://themindzone.pages.dev/idle-supermarket-tycoon.html)
- [CATEGORY CASUAL 6](https://theskillquest.pages.dev/category-casual-6.html)
- [CATEGORY MINECRAFT 2](https://theskillquest.pages.dev/category-minecraft-2.html)
- [CATEGORY MEDIEVAL15](https://theskillquest.pages.dev/category-medieval15.html)
- [CATEGORY BUBBLE SHOOTER27](https://theskillquest.pages.dev/category-bubble-shooter27.html)
- [CATEGORY STRATEGY](https://themindzone.pages.dev/category-strategy.html)
- [INDEX34](https://theskillquest.pages.dev/index34.html)
- [CATEGORY IDLE](https://theskillquest.pages.dev/category-idle.html)
- [CATEGORY FASHION105](https://theskillquest.pages.dev/category-fashion105.html)
- [IDLE DAIRY FARM TYCOON](https://themindzone.pages.dev/idle-dairy-farm-tycoon.html)
- [BRICK BLAZE](https://themindzone.pages.dev/brick-blaze.html)
- [CATEGORY MONSTER206](https://theskillquest.pages.dev/category-monster206.html)
- [CATEGORY MINECRAFT](https://theskillquest.pages.dev/category-minecraft.html)
- [CATEGORY FPS 2](https://theskillquest.pages.dev/category-fps-2.html)
- [HEIST DEFENDER](https://themindzone.pages.dev/heist-defender.html)
- [ROBOT BAND FIND THE DIFFERENCES](https://themindzone.pages.dev/robot-band-find-the-differences.html)
- [CATEGORY MAKEUP](https://theskillquest.pages.dev/category-makeup.html)
- [CATEGORY AVOID295](https://theskillquest.pages.dev/category-avoid295.html)
- [WORD SEARCH UNIVERSE 2](https://themindzone.pages.dev/word-search-universe-2.html)
- [CATEGORY CARTOON76](https://theskillquest.pages.dev/category-cartoon76.html)
- [CATEGORY MOBILE2 095](https://theskillquest.pages.dev/category-mobile2-095.html)
- [IDLE MERGE CAR AND RACE](https://themindzone.pages.dev/idle-merge-car-and-race.html)
- [FUTURE WAR BOT BATTLE IN SPACE 3D](https://themindzone.pages.dev/future-war-bot-battle-in-space-3d.html)
- [JELI2D](https://themindzone.pages.dev/jeli2d.html)
- [CATEGORY CASUAL 13](https://theskillquest.pages.dev/category-casual-13.html)
- [CATEGORY NATIVEGAMES](https://theskillquest.pages.dev/category-nativegames.html)
- [MURDER MYSTERY](https://themindzone.pages.dev/murder-mystery.html)
- [CATEGORY MATCH 3 2](https://theskillquest.pages.dev/category-match-3-2.html)
- [DARTS JAM](https://theskillquest.pages.dev/darts-jam.html)
- [ELLIE CHINESE NEW YEAR CELEBRATION](https://themindzone.pages.dev/ellie-chinese-new-year-celebration.html)
- [TILE FRUITS](https://themindzone.pages.dev/tile-fruits.html)
- [CATEGORY BASKETBALL](https://theskillquest.pages.dev/category-basketball.html)
- [WORD SCRAMBLE FAMILY TALES](https://themindzone.pages.dev/word-scramble-family-tales.html)
- [STARRY STYLE DORAMA OF DREAM](https://themindzone.pages.dev/starry-style-dorama-of-dream.html)
- [CATEGORY CASUAL 4](https://theskillquest.pages.dev/category-casual-4.html)
- [INDEX14](https://theskillquest.pages.dev/index14.html)
- [PANDA DASH AUTO SHOOTING](https://theskillquest.pages.dev/panda-dash-auto-shooting.html)
- [WORM APPLE QUEST](https://themindzone.pages.dev/worm-apple-quest.html)
- [CARDS KLONDIKE SOLITAIRE](https://themindzone.pages.dev/cards-klondike-solitaire.html)
- [CATEGORY PIXEL313](https://iskillquest.pages.dev/category-pixel313.html)
- [GRANNYS CLASSROOM NIGHTMARE](https://theskillquest.pages.dev/grannys-classroom-nightmare.html)
- [SUITABLE OUTFIT DRESSUP](https://iskillquest.pages.dev/suitable-outfit-dressup.html)
- [CATEGORY OBBY](https://theskillquest.pages.dev/category-obby.html)
- [SUPER RACING GT DRAG PRO](https://theskillquest.pages.dev/super-racing-gt-drag-pro.html)
- [3D MATCH PUZZLE MANIA](https://theskillquest.pages.dev/3d-match-puzzle-mania.html)
- [SAND LOOP](https://theskillquest.pages.dev/sand-loop.html)
- [GTA GRAND VEGAS CRIME](https://iskillquest.pages.dev/gta-grand-vegas-crime.html)
- [DINO SIMULATOR CITY ATTACK](https://thequizzone.pages.dev/dino-simulator-city-attack.html)
- [POP FRUIT](https://thequizzone.pages.dev/pop-fruit.html)
- [MR DRIFTER CAR CHASE SIMULATOR](https://iskillquest.pages.dev/mr-drifter-car-chase-simulator.html)
- [CATEGORY MAHJONG 2](https://thequizzone.pages.dev/category-mahjong-2.html)
- [OM NOM RUN](https://theskillquest.pages.dev/om-nom-run.html)
- [CATEGORY FPS 2](https://themindplay.github.io/category-fps-2.html)
- [MOTO STUNT BIKER](https://theskillquest.pages.dev/moto-stunt-biker.html)
- [CATEGORY PUZZLE 12](https://thequizzone.pages.dev/category-puzzle-12.html)
- [PET CONNECT MATCH](https://iskillquest.pages.dev/pet-connect-match.html)
- [HOME BLOCK STORY](https://themindplay.github.io/home-block-story.html)
- [CATEGORY MOUSE1 707 2](https://thequizzone.pages.dev/category-mouse1-707-2.html)
- [CATEGORY MISSION207](https://thequizzone.pages.dev/category-mission207.html)
- [HORROR ESCAPE GRANNY ROOM](https://themindzone.pages.dev/horror-escape-granny-room.html)
- [CATEGORY ESCAPE 3](https://thequizzone.pages.dev/category-escape-3.html)
- [CATEGORY HAPARA](https://thequizzone.pages.dev/category-hapara.html)
- [CATEGORY ESCAPE 2](https://thequizzone.pages.dev/category-escape-2.html)
- [GT CARS MEGA RAMPS](https://iskillquest.pages.dev/gt-cars-mega-ramps.html)
- [CATEGORY MINECRAFT 3](https://thequizzone.pages.dev/category-minecraft-3.html)
- [BEST FRIENDS PUZZLE](https://studyplaying.github.io/best-friends-puzzle.html)
- [WILD HUNTING CLASH](https://themindzone.pages.dev/wild-hunting-clash.html)
- [CATEGORY PUZZLE 2](https://quizverses.github.io/category-puzzle-2.html)
- [CATEGORY PREMIUM PERKS74](https://themindzone.pages.dev/category-premium-perks74.html)
- [CATEGORY MISSION206](https://thequizzone.pages.dev/category-mission206.html)
- [CATEGORY FLASH 2](https://studyplaying.github.io/category-flash-2.html)
- [TRAIN DRIFT](https://studyquesthub.web.app/train-drift.html)
- [CATEGORY BATTLE](https://studyquests.github.io/category-battle.html)
- [WALKERS ATTACK](https://themindzone.pages.dev/walkers-attack.html)
- [KLONDIKE SOLITAIRE](https://quizverses.github.io/klondike-solitaire.html)
- [PLANET HOPPER](https://learnquester.github.io/planet-hopper.html)
- [100 ROOMS ESCAPE](https://studyplayings.web.app/100-rooms-escape.html)
- [CATEGORY PUZZLE 3](https://studyquests.pages.dev/category-puzzle-3.html)
- [CATEGORY DRESS UP 3](https://thequizzone.pages.dev/category-dress-up-3.html)
- [CATEGORY GUN238](https://thequizzone.pages.dev/category-gun238.html)
- [FALLING MAN](https://studyquesthub.web.app/falling-man.html)
- [CATEGORY FASHION](https://quizverses.github.io/category-fashion.html)
- [MAHJONG LINES](https://studyquesthub.web.app/mahjong-lines.html)
- [ADDICTION MINI SOLITAIRE](https://theskillquest.pages.dev/addiction-mini-solitaire.html)
- [POXEL IO](https://studyquests.github.io/poxel-io.html)
- [CATEGORY SCHOOL](https://thequizzone.pages.dev/category-school.html)
- [FALLING ART RAGDOLL SIMULATOR](https://studyquests.github.io/falling-art-ragdoll-simulator.html)
- [CATEGORY CASUAL 5](https://themindplay.github.io/category-casual-5.html)
- [CATEGORY PREMIUM PERKS71](https://thequizzone.pages.dev/category-premium-perks71.html)
- [ZINDEX](https://iskillquest.pages.dev/zindex.html)
- [SIBERIAN ASSAULT](https://quizverses.github.io/siberian-assault.html)
- [IBIZA FOAM PARTY](https://iskillquest.pages.dev/ibiza-foam-party.html)
- [CATEGORY STICKMAN](https://thelearnquester.web.app/category-stickman.html)
- [BATTLE ARENA](https://studyquests.github.io/battle-arena.html)
- [CATEGORY CAR 2](https://studyplayings.pages.dev/category-car-2.html)
- [BRAWL STARS SOUND](https://studyplayings.web.app/brawl-stars-sound.html)
- [CATEGORY MERGE GAMES](https://thequizzone.pages.dev/category-merge-games.html)
- [BANK ROBBERY 3](https://studyplayings.web.app/bank-robbery-3.html)
- [CATEGORY PUZZLE 11](https://thequizzone.pages.dev/category-puzzle-11.html)
- [SWIPETOWN](https://studyquests.pages.dev/swipetown.html)
- [CATEGORY ADVENTURE](https://thelearnquester.web.app/category-adventure.html)
- [CATEGORY PUZZLE 2](https://thequizzone.pages.dev/category-puzzle-2.html)
- [STICKMAN PRISON ESCAPE](https://theskillquest.pages.dev/stickman-prison-escape.html)
- [HOTEL MANAGER](https://studyplayings.web.app/hotel-manager.html)
- [CATEGORY PUZZLE 3](https://theskillquest.pages.dev/category-puzzle-3.html)
- [MOON LEAGUE SPORTS SEASON](https://learnquester.github.io/moon-league-sports-season.html)
