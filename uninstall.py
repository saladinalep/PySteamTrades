#!/usr/bin/env python3
import os, sys, subprocess

try:
    os.chdir(os.path.dirname(sys.executable))
    ret = subprocess.call([sys.executable, '-m', 'pip', 'uninstall', 'PySteamTrades'])
    if ret != 0:
        sys.stderr.write('Error uninstalling PySteamTrades\n')

    if sys.platform == 'win32':
        # delete desktop shortcut
        import pythoncom
        from win32com.shell import shell, shellcon
        desktopFolder = shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOP, 0, 0)
        os.remove(os.path.join(desktopFolder, "PySteamTrades.lnk"))
except:
    pass

