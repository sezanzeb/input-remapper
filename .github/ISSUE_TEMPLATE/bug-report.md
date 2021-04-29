---
name: Bug report
about: Something is not working correctly
title: ''
labels: ''
assignees: ''

---

Please install the newest version from source to see if the problem has already been solved.

1. `key-mapper-control --version`
2. which linux distro (ubuntu 20.04, manjaro, etc.)
3. `echo $XDG_SESSION_TYPE`
4. which desktop environment (gnome, plasma, xfce4, etc.)
5. `sudo ls -l /proc/1/exe`

**Buttons now showing up**

1. If a button on your device doesn't show up in the GUI, verify that the button is reporting an event via `sudo evtest`. If not, key-mapper won't be able to map that button.
2. If yes, please run `sudo pkill -f key-mapper-service && key-mapper-gtk -d`, reproduce the problem and then share the logs.

**Key not getting injected**

1. `sudo pkill -f key-mapper-service && key-mapper-gtk -d`, start the injection and hit your key. Then share that log.
2. `sudo evtest` would also be interesting while the first command is still running, to see how your mapped are injected.

**Autoloading not working**

1. `cat ~/.config/key-mapper/config.json`
2. `key-mapper-control --command hello`
3. Run `sudo pkill -f key-mapper-service && sudo key-mapper-service -d & sleep 2 && key-mapper-control --command autoload` and share the logs.
4. Afterwards (while the previous command is still running) run `sudo evtest` and search for a device suffixed by "mapped". Select it, does it report any events? Share the output.
