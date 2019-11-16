import setuptools, os, sys, subprocess
import setuptools.command.build_py
from setuptools import Command
from setuptools.command.install import install
from glob import glob

def RequirePackage(importName, packageName):
    result = False
    try:
        import importlib
        importlib.import_module(importName)
        result = True
    except:
        print("Package {} required to continue. Trying to install it using pip".format(packageName))
        ret = subprocess.call([sys.executable, '-m', 'pip', 'install', packageName])
        result = (ret == 0)
    return result

class CompileUiCommand(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def compile(self, infile, outfile):
        f = open(outfile, 'w')
        self.uic.compileUi(infile, f)
        f.close()
    def run(self):
        print("Compiling UI files...")
        try:
            # make sure we have pyqtwebengine now so we can use uic
            if not RequirePackage('PyQt5.QtWebEngineWidgets', 'pyqtwebengine'):
                sys.exit(1)
            from PyQt5 import uic
            self.uic = uic
            # compile ui files
            for uiFile in glob(os.path.join('PySteamTrades', '*.ui')):
                directory, fileName = os.path.split(uiFile)
                pyFile = os.path.join(directory, 'Ui_' + fileName.replace('.ui', '.py'))
                print("Compiling: {0} -> {1}".format(uiFile, pyFile))
                self.compile(uiFile, pyFile)
        except Exception as e:
            sys.stderr.write("Error compiling UI files: {}\n".format(str(e)))
            sys.exit(1)

class InstallCommand(install):
    def run(self):
        install.do_egg_install(self)
        if sys.platform == 'win32':
            # create desktop shortcut
            print("Creating desktop shortcut")
            if RequirePackage('pythoncom', 'pywin32'):
                args = [sys.executable, os.path.join(os.path.dirname(__file__), 'win32_shortcut.py')]
                subprocess.call(args)
            else:
                sys.stderr.write('pywin32 unavailable. Cannot create desktop shortcut\n')

class BuildPyCommand(setuptools.command.build_py.build_py):
  def run(self):
    self.run_command('compile_ui')
    setuptools.command.build_py.build_py.run(self)

setuptools.setup(
    name="PySteamTrades",
    version="0.0.1",
    author="Saladin Alep",
    author_email="saladinalep@outlook.com",
    description="Message notifications for SteamTrades.com",
    url="https://github.com/saladinalep/PySteamTrades",
    packages=setuptools.find_packages(),
    # the pyqtwebengine requirement is handled when compiling ui files
    # and pywin32 when creating the desktop shortcut on Windows
    install_requires=['keyring', 'bs4'],
    cmdclass = {'compile_ui': CompileUiCommand, 'build_py': BuildPyCommand, 'install': InstallCommand},
    package_data={'': ['*.ico'],},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
