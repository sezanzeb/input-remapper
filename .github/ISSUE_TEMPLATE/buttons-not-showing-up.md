---
name: Buttons not showing up
about: "..."
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

6. If a button on your device doesn't show up in the GUI, verify that the button is reporting an event via `sudo evtest`. If not, key-mapper won't be able to map that button.
7. If yes, please run `sudo pkill -f key-mapper-service && key-mapper-gtk -d`, reproduce the problem and then share the logs.
