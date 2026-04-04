@echo off
setlocal

set "ROOT=%~dp0"
set "WEB_DIR=%ROOT%apps\web"

if not exist "%WEB_DIR%" (
  echo [ERROR] Cannot find apps\web folder.
  echo Expected: %WEB_DIR%
  pause
  exit /b 1
)

pushd "%WEB_DIR%"

if not exist "package.json" (
  echo [ERROR] package.json not found in apps\web
  pause
  popd
  exit /b 1
)

npm run dev

popd
pause
