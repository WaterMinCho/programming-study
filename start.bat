@echo off
rem Windows: double-click to open the study window without a console.
chcp 65001 >nul
cd /d "%~dp0"
if "%STUDY_CONSOLE%"=="1" goto console
goto window
rem An old start.bat still running resumes at byte 230: exit.
exit /b
:window
where pyw >nul 2>nul && start "" pyw start.pyw && exit /b
where pythonw >nul 2>nul && start "" pythonw start.pyw && exit /b
:console
rem STUDY_CONSOLE=1 comes from bootstrap.hand_off. Without pythonw it also runs here, in this console.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 study.py
) else (
    python study.py
)
if %errorlevel%==9009 echo Python 을 찾지 못했습니다. https://www.python.org/downloads/latest/python3.14/ 에서 Python 3.14 를 설치한 뒤 다시 실행해 주세요.
if not %errorlevel%==0 pause
