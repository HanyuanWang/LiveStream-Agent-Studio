@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".env" copy /y ".env.example" ".env" >nul
echo 即将打开本机配置文件。
echo 请把密钥只粘贴到这个文件里，不要发送到聊天或其他地方。
start "" notepad.exe ".env"

