@echo off
REM Batch file to activate Poetry environment.

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

REM Display what environment will be activated.
py -m poetry env info
echo.

REM Ensure dependencies are installed.
py -m poetry install

REM Use Poetry to get the activation command.
for /f "tokens=* usebackq" %%i in (`py -m poetry env activate`) do set POETRY_ACTIVATE=%%i

if not defined POETRY_ACTIVATE (
    echo Poetry did not return an activation command.
    echo py -m poetry env activate
    pause
    exit /b 1
)

REM Activate the virtual environment in a command shell.
cmd /k %POETRY_ACTIVATE%
