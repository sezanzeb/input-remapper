---
name: Buttons not showing up / Can't map a key in the GUI
about: "..."
title: ''
labels: ''
assignees: ''

---

Please install the newest version from source to see if the problem has already been solved.

Share some logs please:

1. `key-mapper-control --version`
2. which linux distro (ubuntu 20.04, manjaro, etc.)
3. which desktop environment (gnome, plasma, xfce4, etc.)
4. `sudo ls -l /proc/1/exe`

5. If a button on your device doesn't show up in the GUI, verify that the button is reporting an event via `sudo evtest`. If not, key-mapper won't be able to map that button.
6. If yes, please run `sudo pkill -f key-mapper-service && key-mapper-gtk -d`, reproduce the problem and then share the logs.
