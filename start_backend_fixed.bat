@echo off
setlocal

set "ROOT=%~dp0"
set "API_DIR=%ROOT%apps\api"

if not exist "%API_DIR%" (
  echo [ERROR] Cannot find apps\api folder.
  echo Expected: %API_DIR%
  pause
  exit /b 1
)

pushd "%API_DIR%"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo [WARN] .venv not found. Using system Python.
)

if not exist ".env" (
  echo [WARN] .env not found in apps\api
)

uvicorn app.main:app --reload --port 8000

popd
pause
