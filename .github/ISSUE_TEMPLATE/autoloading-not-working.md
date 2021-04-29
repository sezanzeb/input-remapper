---
name: Autoloading not working
about: "..."
title: ''
labels: ''
assignees: ''

---

Please install the newest version from source to see if the problem has already been solved.

Share some logs please:

1. `key-mapper-control --version`
2. which linux distro (ubuntu 20.04, manjaro, etc.)
3. `echo $XDG_SESSION_TYPE`
4. which desktop environment (gnome, plasma, xfce4, etc.)
5. `sudo ls -l /proc/1/exe`

6. `cat ~/.config/key-mapper/config.json`
7. `key-mapper-control --command hello`
8. `systemctl status key-mapper -n 50`
9. `sudo pkill -f key-mapper-service && sudo key-mapper-service -d & sleep 2 && key-mapper-control --command autoload`, are your keys mapped now?
10. (while the previous command is still running) `sudo evtest` and search for a device suffixed by "mapped". Select it, does it report any events? Share the output.
