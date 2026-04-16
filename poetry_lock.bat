@echo off
REM Batch file to update the Poetry lock file.

REM Change to the project directory.
cd /d "%~dp0"

REM Check if Python Install Manager is installed.
where py >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python launcher "py" is not installed or not in PATH.
    echo See DEVELOPMENT.md for instructions.
    pause
    exit /b 1
)

REM Check if Poetry is available via Python launcher.
py -m poetry --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Poetry is not available via "py -m poetry".
    echo See DEVELOPMENT.md for instructions.
    pause
    exit /b 1
)

REM Update the lock file.
py -m poetry lock
