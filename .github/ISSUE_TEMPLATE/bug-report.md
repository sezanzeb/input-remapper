---
name: Bug report
about: Something is not working correctly
title: ''
labels: ''
assignees: ''

---

Please install the newest version from source to see if the problem has already been solved.

If a button on your device doesn't show up in the gui, verify that the button is reporting an event via `sudo evtest`. If not, key-mapper won't be able to map that button.

If yes, please run `sudo systemctl stop key-mapper && key-mapper-gtk -d`, reproduce the problem and then share the logs.
