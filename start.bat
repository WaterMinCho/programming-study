@echo off
rem Windows: double-click to open the study window without a console.
chcp 65001 >nul
cd /d "%~dp0"
if "%STUDY_CONSOLE%"=="1" goto console
goto window
rem An old start.bat still running resumes at byte 230: exit.
exit /b
:window
:console
setlocal DisableDelayedExpansion
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_python.ps1" -Root "%CD%"
set "study_exit=%errorlevel%"
if not "%study_exit%"=="0" pause
exit /b %study_exit%
