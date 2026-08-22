@echo off
cd /d "%~dp0"
if not exist "%~dp0workspace" mkdir "%~dp0workspace"
start "" "%~dp0workspace"

