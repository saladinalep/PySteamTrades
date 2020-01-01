# PySteamTrades
Message notifications and search helper for SteamTrades.com

This is my first Python project. It was an exercise for learning Python and PyQt.

It notifies you of new messages on SteamTrades.com via the system tray or by email. It can also search trade pages automatically for games on your lists, and provide the results of all searches in a single view.

## Installation
You need to install Python first. I tested using Python 3.6.8 on Ubuntu and [3.8.1](https://www.python.org/ftp/python/3.8.1/python-3.8.1-amd64.exe) on Windows, but any version since 3.5 should work.

Once Python is installed clone PySteamTrades, or download it as a zip file and extract it somewhere, then:

### Windows
Run the file `install.bat`

This will download the required dependencies, compile UI files and install everything to the sub-folder `venv-PST` within your current directory. It will also create a desktop shortcut.

### Linux
Open a terminal and `cd` to where the file `setup.py` is located. Create a [venv](https://docs.python.org/3/library/venv.html) and activate it:

```
python3 -m venv ~/venv-PST
. ~/venv-PST/bin/activate
```
This will now install PySteamTrades and its dependencies to `~/venv-PST`

```python3 setup.py install```

Launch it with:

```python3 -m PySteamTrades.main```

## Uninstallation

### Windows

Run the file `uninstall.bat`

### Linux
Open a terminal and `cd` to where you cloned or extracted the files as before, then run:

```
. ~/venv-PST/bin/activate
python3 -m pip uninstall PySteamTrades
```

## Notes
* OAuth2 for Gmail is not implemented yet. If you want to use a Gmail address as the sender of email notifications you should enable 2-step verification for that address, then you can generate an app password to use here. The alternative is to allow less secure apps to access your Gmail account, which is not recommended.
* The search function can be expanded and optimized, which is what I'm considering next. Right now we're doing full-text search without indexing and returning only exact matches.

## Acknowledgments
The icons are from the [Pretty Office 2](http://www.customicondesign.com/pretty-office-icon-part-2/) icon set.
