@echo off
cd /d "%~dp0"
"C:\Python313\python.exe" -u main.py >> automation.log 2>&1
