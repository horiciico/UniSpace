@echo off
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
    echo UniSpace virtual environment ^(.venv^) activated.
) else (
    echo Error: Virtual environment not found at %~dp0.venv
)

