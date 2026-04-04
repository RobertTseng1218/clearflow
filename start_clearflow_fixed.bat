@echo off
setlocal

set "ROOT=%~dp0"

start "ClearFlow Backend" cmd /k ""%ROOT%start_backend_fixed.bat""
start "ClearFlow Frontend" cmd /k ""%ROOT%start_frontend_fixed.bat""
