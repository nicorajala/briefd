If you want to use briefd as a service place the briefd.service file into

`~/.config/systemd/user/briefd.service`

Then:

`systemctl --user enable briefd`

`systemctl --user start briefd`