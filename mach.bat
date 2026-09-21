@echo off
setlocal
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0mach" %*
) else (
  python "%~dp0mach" %*
)
exit /b %errorlevel%
