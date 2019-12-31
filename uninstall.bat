call venv-PST\Scripts\activate
cd \
python -m pip uninstall PySteamTrades
python -c "import PySteamTrades" > nul 2>&1
if /i "%ERRORLEVEL%" neq "0" (
    del %USERPROFILE%\Desktop\PySteamTrades.lnk
)
pause
