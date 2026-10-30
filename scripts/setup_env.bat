@echo off
rem Allows the AI assistant to self-configure paths during session start on Windows
set "PYTHONPATH=%PYTHONPATH%;%CD%\scripts"
echo CodeBin environment initialized successfully.
