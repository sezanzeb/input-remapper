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
2. If a button on your device doesn't show up in the GUI, verify that the button is reporting an event via `sudo evtest`. If not, key-mapper won't be able to map that button.
3. If yes, please run `key-mapper-gtk -d`, reproduce the problem and then share the logs.
