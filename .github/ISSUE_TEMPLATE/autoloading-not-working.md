---
name: Autoloading not working
about: "..."
title: ''
labels: ''
assignees: ''

---

Please install the newest version from source to see if the problem has already been solved.

**System Information and logs**

1. `input-remapper-control --version`
2. which linux distro (ubuntu 20.04, manjaro, etc.)
3. which desktop environment (gnome, plasma, xfce4, etc.)
4. `sudo ls -l /proc/1/exe` to check if you are using systemd
5. `cat ~/.config/input-remapper-2/config.json` to see if the "autoload" config is written correctly
6. `systemctl status input-remapper -n 50` the service has to be running

**Testing the setup**

1. `input-remapper-control --command hello`
2. `sudo pkill -f input-remapper-service && sudo input-remapper-service -d & sleep 2 && input-remapper-control --command autoload`, are your keys mapped now?
3. (while the previous command is still running) `sudo evtest` and search for a device suffixed by "mapped". Select it, does it report any events? Share the output.
4. `sudo udevadm control --log-priority=debug && sudo udevadm control --reload-rules && journalctl -f | grep input-remapper`, now plug in the device that should autoload
