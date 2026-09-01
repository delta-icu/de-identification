@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo Greek Medical Report Anonymizer
echo.

set "CONDA_ENV_NAME=greek-med-anonymizer"
set "CONDA_PY_VERSION=3.11"
set "APP_PORT=8501"
set "APP_URL=http://localhost:%APP_PORT%"

set "PY_CMD="
set "ENV_LABEL="

REM ---------------------------------------------------------------------------
REM Stage 1: an already-active conda environment, if it is new enough
REM ---------------------------------------------------------------------------

if defined CONDA_PREFIX (
  if exist "%CONDA_PREFIX%\python.exe" (
    call :version_ok "%CONDA_PREFIX%\python.exe"
    if !errorlevel! equ 0 (
      set "PY_CMD=%CONDA_PREFIX%\python.exe"
      set "ENV_LABEL=active conda environment"
    ) else (
      echo Active conda environment has an unsupported Python; skipping it.
    )
  )
)

REM ---------------------------------------------------------------------------
REM Stage 2: an existing .venv, if it is new enough (otherwise rebuild it)
REM ---------------------------------------------------------------------------

if not defined PY_CMD (
  if exist ".venv\Scripts\python.exe" (
    call :version_ok ".venv\Scripts\python.exe"
    if !errorlevel! equ 0 (
      set "PY_CMD=.venv\Scripts\python.exe"
      set "ENV_LABEL=local .venv"
    ) else (
      echo Existing .venv has an unsupported Python; removing it.
      rmdir /s /q ".venv"
    )
  )
)

REM ---------------------------------------------------------------------------
REM Stage 3: any suitable Python on the system -^> build a fresh .venv
REM ---------------------------------------------------------------------------

if not defined PY_CMD (
  set "BASE_PY="
  for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined BASE_PY (
      py -%%V -c "import sys" >nul 2>nul
      if !errorlevel! equ 0 set "BASE_PY=py -%%V"
    )
  )
  if not defined BASE_PY (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
      call :version_ok "python"
      if !errorlevel! equ 0 set "BASE_PY=python"
    )
  )

  if defined BASE_PY (
    echo Found a suitable Python. Creating local virtual environment...
    if exist ".venv" rmdir /s /q ".venv"
    !BASE_PY! -m venv .venv
    if exist ".venv\Scripts\python.exe" (
      set "PY_CMD=.venv\Scripts\python.exe"
      set "ENV_LABEL=local .venv"
    ) else (
      echo Could not create the virtual environment.
      pause
      exit /b 1
    )
  )
)

REM ---------------------------------------------------------------------------
REM Stage 4: fall back to a dedicated conda environment with a pinned Python
REM ---------------------------------------------------------------------------

if not defined PY_CMD (
  set "CONDA_BIN="
  if defined CONDA_EXE if exist "%CONDA_EXE%" set "CONDA_BIN=%CONDA_EXE%"
  if not defined CONDA_BIN (
    for /f "delims=" %%C in ('where conda 2^>nul') do (
      if not defined CONDA_BIN set "CONDA_BIN=%%C"
    )
  )
  if not defined CONDA_BIN (
    for %%G in (
      "%USERPROFILE%\miniconda3\Scripts\conda.exe"
      "%USERPROFILE%\anaconda3\Scripts\conda.exe"
      "%USERPROFILE%\miniforge3\Scripts\conda.exe"
      "%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
      "%LOCALAPPDATA%\Continuum\anaconda3\Scripts\conda.exe"
      "%ProgramData%\Miniconda3\Scripts\conda.exe"
      "%ProgramData%\Anaconda3\Scripts\conda.exe"
    ) do (
      if not defined CONDA_BIN if exist %%G set "CONDA_BIN=%%~G"
    )
  )

  if defined CONDA_BIN (
    echo No suitable Python found on the system. Using conda instead.

    call :conda_env_prefix
    if not defined ENV_PREFIX (
      echo Creating conda environment "%CONDA_ENV_NAME%" with Python %CONDA_PY_VERSION%...
      echo This can take several minutes the first time.
      "!CONDA_BIN!" create -y -n "%CONDA_ENV_NAME%" "python=%CONDA_PY_VERSION%"
      call :conda_env_prefix
    )

    if defined ENV_PREFIX (
      call :version_ok "!ENV_PREFIX!\python.exe"
      if !errorlevel! equ 0 (
        REM Call the environment's interpreter by full path - no activation needed.
        set "PY_CMD=!ENV_PREFIX!\python.exe"
        set "ENV_LABEL=conda environment %CONDA_ENV_NAME%"
      ) else (
        echo Conda environment "%CONDA_ENV_NAME%" has an unsupported Python; updating it...
        "!CONDA_BIN!" install -y -n "%CONDA_ENV_NAME%" "python=%CONDA_PY_VERSION%"
        call :version_ok "!ENV_PREFIX!\python.exe"
        if !errorlevel! equ 0 (
          set "PY_CMD=!ENV_PREFIX!\python.exe"
          set "ENV_LABEL=conda environment %CONDA_ENV_NAME%"
        )
      )
    )
  )
)

REM ---------------------------------------------------------------------------
REM Nothing worked: explain exactly what to do
REM ---------------------------------------------------------------------------

if not defined PY_CMD (
  echo.
  echo This app needs Python 3.10 or newer, and none was found.
  echo.
  echo Pick one of these, then run this file again:
  echo.
  echo   1. Install Python from https://www.python.org/downloads/
  echo      During setup, tick "Add python.exe to PATH".
  echo.
  echo   2. Or, if you use conda, run this once in Anaconda Prompt:
  echo      conda create -n %CONDA_ENV_NAME% python=%CONDA_PY_VERSION% -y
  echo.
  pause
  exit /b 1
)

echo Using %ENV_LABEL%.

REM ---------------------------------------------------------------------------
REM Dependencies
REM ---------------------------------------------------------------------------

"%PY_CMD%" -c "import streamlit, torch, transformers" >nul 2>nul
if errorlevel 1 (
  echo Installing required packages. The first time this can take several minutes...
  "%PY_CMD%" -m pip install --upgrade pip
  "%PY_CMD%" -m pip install -e ".[ml,ui]"
  if errorlevel 1 (
    echo Could not install the required packages.
    pause
    exit /b 1
  )

  "%PY_CMD%" -c "import streamlit, torch, transformers" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo Packages are installed, but one of them will not load. Details:
    "%PY_CMD%" -c "import streamlit, torch, transformers"
    echo.
    pause
    exit /b 1
  )
)

REM ---------------------------------------------------------------------------
REM Launch
REM ---------------------------------------------------------------------------

REM Streamlit shows a one-time "enter your email" prompt on a fresh install and
REM waits for input, which stalls the launch. Pre-creating the credentials file
REM with an empty email skips it. Never overwrite an existing one.
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
  > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
  >>"%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo Launching web app...
echo The browser will open at %APP_URL% once the app is ready.
echo Close this window or press Ctrl+C to stop the app.
echo.

REM Open the browser shortly after the server starts.
start "" /b cmd /c "timeout /t 8 /nobreak >nul & start %APP_URL%"

"%PY_CMD%" -m streamlit run src\greek_med_anonymizer\web_app.py ^
  --server.port=%APP_PORT% ^
  --server.headless=true ^
  --browser.gatherUsageStats=false

set "STATUS=%errorlevel%"
if not "%STATUS%"=="0" (
  echo.
  echo The web app stopped with an error ^(exit code %STATUS%^). See the messages above.
  echo.
  pause
)

endlocal
exit /b 0

REM ---------------------------------------------------------------------------
REM Subroutines
REM ---------------------------------------------------------------------------

:version_ok
REM %1 = python command. Sets errorlevel 0 when it is 3.10 or newer.
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
exit /b %errorlevel%

:conda_env_prefix
REM Sets ENV_PREFIX to the named environment's folder, or leaves it empty.
set "ENV_PREFIX="
for /f "delims=" %%P in ('""!CONDA_BIN!" run -n "%CONDA_ENV_NAME%" python -c "import sys;print(sys.prefix)"" 2^>nul') do (
  set "ENV_PREFIX=%%P"
)
exit /b 0
