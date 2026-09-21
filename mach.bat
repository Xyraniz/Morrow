@echo off
setlocal

where.exe vpython3 >nul 2>nul
if not errorlevel 1 goto run_vpython3

where.exe py >nul 2>nul
if not errorlevel 1 goto run_py

where.exe python >nul 2>nul
if not errorlevel 1 goto run_python

>&2 echo Could not find vpython3, py, or python on PATH.
exit /b 9009

:run_vpython3
vpython3 "%~dp0mach" %*
exit /b %errorlevel%

:run_py
py -3 "%~dp0mach" %*
exit /b %errorlevel%

:run_python
python "%~dp0mach" %*
exit /b %errorlevel%
