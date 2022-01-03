---
name: Autoloading not working
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

6. `cat ~/.config/input-remapper/config.json`
7. `input-remapper-control --command hello`
8. `systemctl status input-remapper -n 50`
9. `sudo pkill -f input-remapper-service && sudo input-remapper-service -d & sleep 2 && input-remapper-control --command autoload`, are your keys mapped now?
10. (while the previous command is still running) `sudo evtest` and search for a device suffixed by "mapped". Select it, does it report any events? Share the output.
