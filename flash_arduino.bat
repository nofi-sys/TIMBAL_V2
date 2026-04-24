@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0flash_arduino.ps1" %*
exit /b %errorlevel%
