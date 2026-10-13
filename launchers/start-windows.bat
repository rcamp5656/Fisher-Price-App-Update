@echo off
setlocal
title Fisher-Price Record Maker
cd /d "%~dp0"
echo.
echo  ======================================================
echo   Fisher-Price Record Maker  -  one-click local start
echo   Dedicated To My Fiancee Barbara - (c) 2026 Russ Campbell
echo  ======================================================
echo.

where python >nul 2>nul || (
  echo  [!] Python 3.10+ not found.  Install from https://www.python.org/downloads/
  echo      and tick "Add python.exe to PATH" in the installer, then run this file again.
  pause & exit /b 1
)
where node >nul 2>nul || (
  echo  [!] Node.js not found.  Install the LTS version from https://nodejs.org/
  echo      then run this file again.
  pause & exit /b 1
)

where mongod >nul 2>nul
if %errorlevel%==0 (
  if not exist "data\db" mkdir "data\db"
  echo  [1/4] Starting MongoDB ^(data\db^) ...
  start "FP MongoDB" /min cmd /c "mongod --dbpath data\db --port 27017"
  set STORAGE=mongo
) else (
  echo  [1/4] MongoDB not found - records will be saved as files in  data\records  ^(no install needed^).
  set STORAGE=files
)

echo  [2/4] Backend: Python packages ...
if not exist "backend\.venv" python -m venv backend\.venv
call backend\.venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r backend\requirements-local.txt || (echo  [!] pip install failed & pause & exit /b 1)
if not exist "backend\.env" (
  if "%STORAGE%"=="mongo" (
    > backend\.env echo MONGO_URL=mongodb://localhost:27017
    >> backend\.env echo DB_NAME=fisher_price
  ) else (
    > backend\.env echo FP_STORAGE=files
    >> backend\.env echo DATA_DIR=../data/records
  )
)
start "FP Backend  (http://localhost:8001)" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn server:app --host 0.0.0.0 --port 8001"

echo  [3/4] Frontend: Node packages ^(first run takes a few minutes^) ...
if not exist "frontend\.env" (
  > frontend\.env echo REACT_APP_BACKEND_URL=http://localhost:8001
)
cd frontend
if not exist "node_modules" call npm install --silent --legacy-peer-deps || (echo  [!] npm install failed & pause & exit /b 1)
set BROWSER=none
start "FP Frontend (http://localhost:3000)" cmd /k "cd /d "%~dp0frontend" && set BROWSER=none&& npm start"
cd ..

echo  [4/4] Opening http://localhost:3000 in your browser in 20 s ...
timeout /t 20 >nul
start "" http://localhost:3000
echo.
echo  Done. Keep the two black windows open while you use the app.
echo  Close them (or press Ctrl+C in each) to stop.
pause
