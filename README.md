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
- [IMPOSTER 3D](https://studyplaying.github.io/imposter-3d.html)
- [INDEX9](https://thelearnquester.web.app/index9.html)
- [SNIPING ALIENS](https://studyplayings.pages.dev/sniping-aliens.html)
- [CATEGORY DRESS UP GAMES](https://thelearnquesters.pages.dev/category-dress-up-games.html)
- [CRAFT OF WARS](https://theskillquest.pages.dev/craft-of-wars.html)
- [FISH EAT GROW MEGA](https://theskillquest.pages.dev/fish-eat-grow-mega.html)
- [MASK EVOLUTION 3D](https://themindzone.pages.dev/mask-evolution-3d.html)
- [CITY BUILDER](https://themindplay.pages.dev/city-builder.html)
- [CATEGORY AVOID295](https://theskillquest.pages.dev/category-avoid295.html)
- [ITALIAN BRAINROT NEURO BEASTS](https://themindzone.pages.dev/italian-brainrot-neuro-beasts.html)
- [GAL SLIDING PUZZLE](https://themindplay.github.io/gal-sliding-puzzle.html)
- [HEADLESS JOE](https://themindzone.pages.dev/headless-joe.html)
- [CATEGORY ARCHERY52](https://themindzone.pages.dev/category-archery52.html)
- [DRAW BRIDGE PUZZLE](https://thequizzone.pages.dev/draw-bridge-puzzle.html)
- [INDEX24](https://theskillquest.pages.dev/index24.html)
- [BATTLE OF PIRATE CARIBBEAN BATTLE](https://theskillquest.pages.dev/battle-of-pirate-caribbean-battle.html)
- [PUT THE FRUIT TOGETHER](https://themindzone.pages.dev/put-the-fruit-together.html)
- [PUMPKIN PATCH](https://thequizzone.pages.dev/pumpkin-patch.html)
- [DINOSAUR RAMPAGE](https://thequizzone.pages.dev/dinosaur-rampage.html)
- [GT FORMULA CHAMPIONSHIP](https://thequizzone.pages.dev/gt-formula-championship.html)
- [CATEGORY BATTLE ROYALE25](https://iskillquest.pages.dev/category-battle-royale25.html)
- [NOOB RAGDOLL CRAZY PUNCH](https://themindzone.pages.dev/noob-ragdoll-crazy-punch.html)
- [INDEX8](https://theskillquest.pages.dev/index8.html)
- [ONLINE PORTAL](https://theskillquest.pages.dev/)
- [PUSH TO GO](https://thequizzone.pages.dev/push-to-go.html)
- [WOLF LIFE SIMULATOR](https://themindzone.pages.dev/wolf-life-simulator.html)
- [SOKOBAN PUZZLE GAME](https://iskillquest.pages.dev/sokoban-puzzle-game.html)
- [BUBBLE POP FAIRYLAND](https://thequizzone.pages.dev/bubble-pop-fairyland.html)
- [CATEGORY OBBY](https://iskillquest.pages.dev/category-obby.html)
- [RAINBOW FRIENDS HIDE AND SEEK](https://skillplay.github.io/rainbow-friends-hide-and-seek.html)
- [ENERGY SUPERMAN 3D](https://themindskillplayplay.pages.dev/energy-superman-3d.html)
- [PORTAL MASTER](https://theskillquest.pages.dev/portal-master.html)
- [WAR ROBOTS BATTLES](https://themindskillplayplay.pages.dev/war-robots-battles.html)
- [FRUIT MERGE JUICY DROP GAME](https://themindskillplayplay.pages.dev/fruit-merge-juicy-drop-game.html)
- [ALIENS HUNTER](https://skillplay.web.app/aliens-hunter.html)
- [OBBY VS ZOMBIES](https://theskillquest.pages.dev/obby-vs-zombies.html)
- [PUMPKING VS MUMMY](https://skillplay.web.app/pumpking-vs-mummy.html)
- [FUTURE WAR BOT BATTLE IN SPACE 3D](https://themindzone.pages.dev/future-war-bot-battle-in-space-3d.html)
- [FALLING BLOCKS PUZZLE](https://theskillquest.pages.dev/falling-blocks-puzzle.html)
- [INDEX27](https://theskillquest.pages.dev/index27.html)
- [STICK MASTER TELEPORT](https://skillplay.web.app/stick-master-teleport.html)
- [GOTHIC KNIFE](https://skillplay.web.app/gothic-knife.html)
- [TRUCKTOPOLIS COOKING CHAOS](https://theskillquest.pages.dev/trucktopolis-cooking-chaos.html)
- [POKE THE PRESIDENTS](https://thequizzone.pages.dev/poke-the-presidents.html)
- [RICH CHOICE RUN](https://theskillquest.pages.dev/rich-choice-run.html)
- [CAR CRASH TEST ABANDONED CITY](https://skillplay.web.app/car-crash-test-abandoned-city.html)
- [MAHJONG TOUR](https://skillplay.web.app/mahjong-tour.html)
- [CATEGORY BIKE63](https://themindplay.github.io/category-bike63.html)
- [RAMP CAR JUMPING](https://skillplay.web.app/ramp-car-jumping.html)
- [CATEGORY ADVENTURE 2](https://theskillquest.pages.dev/category-adventure-2.html)
- [KOUR IO](https://skillplay.web.app/kour-io.html)
- [INDEX21](https://theskillquest.pages.dev/index21.html)
- [IDLE BASEBALL TYCOON](https://skillplay.web.app/idle-baseball-tycoon.html)
- [SKIP LOVE](https://skillplay.web.app/skip-love.html)
- [CATEGORY PUZZLE 3](https://themindplay.github.io/category-puzzle-3.html)
- [KING KONG CHAOS](https://skillplay.web.app/king-kong-chaos.html)
- [GALACTIC GOLF SOLITAIRE](https://skillplay.web.app/galactic-golf-solitaire.html)
- [FIND IT OUT COLORFUL BOOK](https://skillplay.web.app/find-it-out-colorful-book.html)
- [MY LITTLE CAR WASH](https://themindzone.pages.dev/my-little-car-wash.html)
- [ZEN SOLITAIRE](https://skillplay.web.app/zen-solitaire.html)
- [GOON BALL](https://skillplay.web.app/goon-ball.html)
- [CATEGORY GROW GAMES](https://themindplay.github.io/category-grow-games.html)
- [SLOPE EMOJI 2](https://skillplay.web.app/slope-emoji-2.html)
- [TRAVEL MAHJONG DELUXE](https://thequizzone.pages.dev/travel-mahjong-deluxe.html)
- [INDEX28](https://theskillquest.pages.dev/index28.html)
- [SANDBOX ISLAND WAR](https://skillplay.web.app/sandbox-island-war.html)
- [TIKTOK TRENDS COLORED DENIM](https://skillplay.web.app/tiktok-trends-colored-denim.html)
- [LABO BRICK TRAIN GAME FOR KIDS](https://iskillquest.pages.dev/labo-brick-train-game-for-kids.html)
- [MEOW SLIDE](https://learnquester.github.io/meow-slide.html)
- [SUPER ELIP ADVENTURE](https://themindskillplayplay.pages.dev/super-elip-adventure.html)
- [POPCORN STACK](https://studyplayings.pages.dev/popcorn-stack.html)
- [DARK MYTH MONKEY MERGE](https://thequizzone.pages.dev/dark-myth-monkey-merge.html)
- [BRAWL BROS SQUAD](https://thelearnquester.web.app/brawl-bros-squad.html)
- [CATEGORY BALL175](https://theskillquest.pages.dev/category-ball175.html)
- [CYBERPUNK AGENT](https://thelearnquesters.pages.dev/cyberpunk-agent.html)
- [MEGA RAMP CAR](https://skillplay.web.app/mega-ramp-car.html)
- [BITGOBLINS RPG SIMULATOR](https://themindzone.pages.dev/bitgoblins-rpg-simulator.html)
- [GEOMETRY ARROW 2](https://learnquester.github.io/geometry-arrow-2.html)
- [PICTURE PUZZLES](https://studyplaying.github.io/picture-puzzles.html)
- [HEROBALL ADVENTURES 2](https://studyplaying.github.io/heroball-adventures-2.html)
- [PARK THEM ALL](https://thequizzone.pages.dev/park-them-all.html)
- [TRIANGLE WAY](https://themindskillplayplay.pages.dev/triangle-way.html)
- [SEA BATTLE ADMIRAL](https://studyplaying.github.io/sea-battle-admiral.html)
- [CS COMMAND SNIPERS](https://themindskillplayplay.pages.dev/cs-command-snipers.html)
- [ROCKET FEST](https://studyplaying.github.io/rocket-fest.html)
- [DAILY CHESS PUZZLE](https://themindskillplayplay.pages.dev/daily-chess-puzzle.html)
- [CAR SIMULATOR 3D CAR GAME 3D](https://thequizzone.pages.dev/car-simulator-3d-car-game-3d.html)
- [JEWEL GARDEN STORY](https://themindplays.pages.dev/jewel-garden-story.html)
- [CAPYBARA BLOCK BLAST](https://themindplays.pages.dev/capybara-block-blast.html)
- [STICKMAN GUNNER](https://learnquester.pages.dev/stickman-gunner.html)
- [GRENADE SIMULATOR](https://studyplaying.github.io/grenade-simulator.html)
- [CATEGORY BUILDING182](https://iskillquest.pages.dev/category-building182.html)
- [LUCY ALL SEASON FASHIONINSTA](https://learnquesters.pages.dev/lucy-all-season-fashioninsta.html)
- [OBBY TOWER PARKOUR CLIMB](https://studyplaying.github.io/obby-tower-parkour-climb.html)
- [MONSTER DUELIST](https://iskillquest.pages.dev/monster-duelist.html)
- [ROBYBOX SPACE STATION WAREHOUSE](https://studyplaying.github.io/robybox-space-station-warehouse.html)
- [MINEBUILD](https://learnquester.pages.dev/minebuild.html)
- [BACTERIA LIFE DEATH](https://skillplay.github.io/bacteria-life-death.html)
- [MERGE SQUARES](https://thelearnquesters.pages.dev/merge-squares.html)
- [BUBBLE SHOOTER BUTTERFLY](https://themindzone.pages.dev/bubble-shooter-butterfly.html)
- [CATEGORY SIMULATION 3](https://thelearnquesters.pages.dev/category-simulation-3.html)
- [NETQUEL COM](https://thequizzone.pages.dev/netquel-com.html)
- [SPACE SURVIVOR](https://studyplaying.github.io/space-survivor.html)
- [MONSTER SCHOOL CHALLENGE](https://themindzone.pages.dev/monster-school-challenge.html)
- [GIRLY PUZZLE](https://themindzone.pages.dev/girly-puzzle.html)
- [ANIMAL LINK](https://themindplaying.web.app/animal-link.html)
- [SPACES SOLITAIRE](https://themindplays.pages.dev/spaces-solitaire.html)
- [THE STONE MINER](https://skillplay.web.app/the-stone-miner.html)
- [FRUIT MAHJONG 3D](https://thelearnquesters.pages.dev/fruit-mahjong-3d.html)
- [WOODS OF NEVIA FOREST SURVIVAL](https://thequizzone.pages.dev/woods-of-nevia-forest-survival.html)
- [CATEGORY MATCH THREE](https://learnquesters.pages.dev/category-match-three.html)
- [MY KITTIES CATWORLD](https://themindplaying.web.app/my-kitties-catworld.html)
- [HORDE HUNTERS](https://studyplayings.web.app/horde-hunters.html)
- [BRAWL STARS BRAVE ADVENTURE](https://studyquests.github.io/brawl-stars-brave-adventure.html)
- [FIND 6 DIFFERENCES SPOT THE HIDDEN CHANGES](https://skillplay.github.io/find-6-differences-spot-the-hidden-changes.html)
- [CUT GRASS](https://learnquester.pages.dev/cut-grass.html)
- [FROST LAND SNOW SURVIVAL](https://skillplay.web.app/frost-land-snow-survival.html)
- [OBBY PRISON RUN](https://themindzone.pages.dev/obby-prison-run.html)
- [SCREW JAM FUN PUZZLE GAME](https://themindzone.pages.dev/screw-jam-fun-puzzle-game.html)
- [CATEGORY DRESS UP](https://iskillquest.pages.dev/category-dress-up.html)
- [CATEGORY FASHION](https://learnquester.github.io/category-fashion.html)
- [CITYIDLE](https://thelearnquesters.pages.dev/cityidle.html)
- [HIGHWAY BUS RUSH](https://skillplay.web.app/highway-bus-rush.html)
- [MERGE CUBE CHALLENGE](https://iskillquest.pages.dev/merge-cube-challenge.html)
- [FREECELL SOLITAIRE](https://skillplay.web.app/freecell-solitaire.html)
- [CATEGORY DRESS UP 2](https://iskillquest.pages.dev/category-dress-up-2.html)
- [LOGIC STORM ANIMALS PUZZLE](https://themindplay.pages.dev/logic-storm-animals-puzzle.html)
- [CATEGORY ADVENTURE 2](https://quizverses.pages.dev/category-adventure-2.html)
- [PARKING MASTER URBAN CHALLENGES](https://skillplay.github.io/parking-master-urban-challenges.html)
- [PAPER DOLL DIARY CHIBI DOLLS](https://themindskillplayplay.pages.dev/paper-doll-diary-chibi-dolls.html)
