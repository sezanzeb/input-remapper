---
name: Key not getting injected
about: "..."
title: ''
labels: ''
assignees: ''

---

Please install the newest version from source to see if the problem has already been solved.

Share some logs please:

1. `input-remapper-control --version`
2. which linux distro (ubuntu 20.04, manjaro, etc.)
3. `echo $XDG_SESSION_TYPE`
4. which desktop environment (gnome, plasma, xfce4, etc.)
5. `sudo ls -l /proc/1/exe`

6. paste the affected preset .json file from ~/.config/input-remapper/presets
7. `sudo pkill -f input-remapper-service && input-remapper-gtk -d`, start the injection and hit your key. Then share that log.
8. `sudo evtest` would also be interesting while the first command is still running, to see how your mappings are injected.
