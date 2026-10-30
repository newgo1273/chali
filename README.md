# chali

Chali means **Chat CLI**: a terminal dashboard for YouTube live chat and Streamlabs alerts. It includes a simulated demo mode, an interactive configuration screen, configurable author badges, and a Debian package layout.

## Features

- `chali --config` opens a Textual setup screen and saves to `~/.config/chali/config.json`.
- `chali` starts the offline demo. `chali URL` also stays in demo mode by default; use `chali --live URL` to connect to YouTube.
- The dashboard has a fixed status/goal/activity header and a scrolling chat area.
- Live YouTube chat uses `pytchat`; viewer counts use `yt-dlp` metadata when available.
- Streamlabs alerts use its Socket.IO endpoint when a socket token is configured.
- The Debian package installs the launcher at `/usr/bin/chali` and application code at `/usr/lib/chali`.

## Install for development

Python 3.9 or newer is required. Install the project and its Python dependencies in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

For a demo, run:

```sh
chali
```

Configure preferences with `chali --config`. To try the live YouTube integration, configure a Streamlabs token if desired, then run:

```sh
chali --live 'https://www.youtube.com/watch?v=VIDEO_ID'
```

Live mode requires the optional Python modules `pytchat`, `yt-dlp`, and `python-socketio`. The project declares them as install-time dependencies for development. The Debian package itself does not run `pip` or access the network during installation; the default demo and configuration remain usable with Debian's `python3` and `python3-textual` packages. Install distro packages for optional live modules when your distribution provides them.

## Configuration

The config file is JSON at `~/.config/chali/config.json`; the config screen creates it with user-only permissions. Settings include demo mode, YouTube defaults, the Streamlabs token, the Fund Bar, goal values, and author badge colors. The badge palette also accepts custom `#RRGGBB` values and rejects combinations below a 4.5:1 contrast ratio. Keep the token private.

## Debian package

The package is architecture-independent (`Architecture: all`) and contains only Python source and a Python launcher. It requires a Debian-based distribution with Python 3.9 or newer and an APT package for Textual (`python3-textual`). The exact package metadata is `packaging/DEBIAN/control`.

Build on Debian or Ubuntu with `dpkg-deb` installed:

```sh
python3 packaging/build_deb.py
```

This creates `dist/chali_0.1.0_all.deb`. `dpkg-deb` builds the archive but does not resolve dependencies; install the declared prerequisites with APT, then install the package:

```sh
sudo apt install python3 python3-pip python3-textual
sudo apt install ./dist/chali_0.1.0_all.deb
```

The package does not execute `pip` at install time. Optional live integrations need `pytchat`, `yt-dlp`, and `python-socketio` available to the system Python; those modules are not guaranteed to be packaged by every Debian derivative. The build script refuses to label the package `all` if it finds compiled native extensions in the app source.

To inspect the archive and metadata:

```sh
dpkg-deb --info dist/chali_0.1.0_all.deb
dpkg-deb --contents dist/chali_0.1.0_all.deb
```

## Debian staging layout

```text
packaging/
  DEBIAN/
    control
  build_deb.py
dist/                         # generated
  chali_0.1.0_all.deb
```

The build script assembles this package root:

```text
DEBIAN/
  control
usr/
  bin/
    chali                 # executable Python launcher
  lib/
    chali/
      chali/              # application package
```

## License

GPL-2.0-or-later. See [COPYING](COPYING).
