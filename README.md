# PySteamTrades
Message notifications for SteamTrades.com

This is my first Python project. It was an exercise for learning Python and PyQt.

It opens a browser window where you can log in to `steamtrades.com`, after which it will check periodically for new messages and notify you via the system tray or by email when it finds any.

## Installation
You need to install Python first. I tested using Python 3.6.8 on Ubuntu and [3.8.0](https://www.python.org/ftp/python/3.8.0/python-3.8.0-amd64.exe) on Windows, but any version since 3.5 should work.

Once Python is installed clone PySteamTrades, or download it as a zip file and extract it somewhere. Open a command prompt and `cd` to where the file `setup.py` is located, then run:

### Windows
```py -m pip install certifi```

This seems necessary to avoid certificate errors with `pip` later. Then:

```py setup.py install```

This will download the required dependencies, compile UI files and install the package to your `site-packages` folder. It will also create a desktop shortcut.

You can launch PySteamTrades using the shortcut or by typing:

```py -m PySteamTrades.main```

### Linux

Create a [venv](https://docs.python.org/3/library/venv.html) and activate it:

```
python3 -m venv ~/PySteamTrades-venv
. ~/PySteamTrades-venv/bin/activate
```
This will now install PySteamTrades and its dependencies to `~/PySteamTrades-venv`

```python3 setup.py install```

Launch it with:

```python3 -m PySteamTrades.main```

## Uninstallation
Open a command prompt and `cd` to where you cloned or extracted the files as before, then run:

### Windows

```py uninstall.py```

### Linux

```python3 uninstall.py```

## Acknowledgments
The icons are from the [Pretty Office 2](http://www.customicondesign.com/pretty-office-icon-part-2/) icon set.
