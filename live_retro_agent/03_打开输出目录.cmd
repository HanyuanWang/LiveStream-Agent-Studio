@echo off
if not exist "%~dp0workspace\output" mkdir "%~dp0workspace\output"
start "" explorer.exe "%~dp0workspace\output"

