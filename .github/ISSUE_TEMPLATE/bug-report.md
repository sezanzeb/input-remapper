---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

Please first install the newest version from source to see if the problem has already been solved first. If there are problems with mapping keys, please run the following, reproduce the problem and then share the logs:

```
sudo systemctl stop key-mapper
sudo key-mapper-gtk -d
```
