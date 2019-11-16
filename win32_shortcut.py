import os, sys

try:
    import pythoncom
    from win32com.shell import shell, shellcon

    shellLink = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None,\
    pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)

    pythonFolder = os.path.dirname(sys.executable)
    target = os.path.join(pythonFolder, 'pythonw.exe')
    shellLink.SetPath(target)
    shellLink.SetArguments('-m PySteamTrades.main')
    shellLink.SetWorkingDirectory(pythonFolder)
    shellLink.SetIconLocation(target, 0)

    desktopFolder = shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOP, 0, 0)
    shortcut = shellLink.QueryInterface(pythoncom.IID_IPersistFile)
    shortcut.Save(os.path.join(desktopFolder, "PySteamTrades.lnk"), 0)
except Exception as e:
    sys.stderr.write("Error creating desktop shortcut: {}\n".format(str(e)))
