@echo off
echo ===================================================
echo  TrialGuard AI - Test Runner
echo ===================================================
echo.

cd /d "%~dp0src\backend"

echo [Step 1] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo FAILED: pip install failed
    pause
    exit /b 1
)

echo.
echo [Step 2] Running MockDataSource test...
python test_mock_datasource.py
if errorlevel 1 (
    echo.
    echo WARNING: MockDataSource test had failures. Fix before continuing.
    pause
)

echo.
echo [Step 2b] Running Data Import unit tests (no DB required)...
pip install pytest >nul 2>&1
pytest test_imports.py -v --tb=short
if errorlevel 1 (
    echo.
    echo WARNING: Import tests had failures.
    pause
)

echo.
echo [Step 3] Starting backend server for API tests...
echo    Starting server in background...
start /B python main.py
echo    Waiting 5 seconds for server startup...
timeout /t 5 /nobreak >nul

echo.
echo [Step 4] Running API endpoint tests...
python test_api_endpoints.py

echo.
echo [Step 5] Stopping background server...
taskkill /f /im python.exe /fi "WINDOWTITLE eq *" >nul 2>&1

echo.
echo ===================================================
echo  All tests complete! Check results above.
echo ===================================================
pause
