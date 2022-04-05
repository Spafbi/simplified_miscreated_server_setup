@echo off
pushd "%~dp0"

:start
set BASEPATH=%~dp0
set BASEPATH=%BASEPATH:~0,-1%

REM If a skip file exists, python won't be checked/downloaded
if exist "%BASEPATH%\stop*" goto :stopMessage

if NOT "%BASEPATH%"=="%BASEPATH: =%" goto :noSpaces

echo Checking for new Simplified Miscreated Server Script updates...
set GITURL=https://api.github.com/repos/Spafbi/simplified_miscreated_server_setup/releases/latest
set DOWNLOADURL=https://github.com/Spafbi/simplified_miscreated_server_setup/releases/download/
set CORESCRIPT=start_server_core.cmd
set DOWNLOAD=0
powershell -Command "$request=${env:GITURL}; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Write-Output (Invoke-WebRequest -UseBasicParsing $request |ConvertFrom-Json |Select tag_name -ExpandProperty tag_name)">latest_release

set CORESCRIPT=smss.py
set PYTHONPTH=python310._pth
set PYTHONVERSION=3.10.4
set PYTHONZIP=python310.zip

set PYTHONURL=https://www.python.org/ftp/python/%PYTHONVERSION%/python-%PYTHONVERSION%-embed-amd64.zip
set PYTHONDIR=%BASEPATH%\python
set PYTHONBIN=%PYTHONDIR%\python.exe
set PIPBIN=%PYTHONDIR%\Scripts\pip.exe
set PIPURL=https://bootstrap.pypa.io/get-pip.py
set SMSSTEMP=%BASEPATH%\temp

REM This if statement exists so I don't overwrite the core script while developing
if exist .\.git\ (
  set TARGETSCRIPT=smss_download.py
) else (
  set TARGETSCRIPT=%CORESCRIPT%
)

REM Set the "local" release version
if exist "local_release" (
  set /p CURRENT=<local_release
) else (
  set CURRENT=0
)

REM Set the "latest" release version
if exist "latest_release" (
  set /p LATEST=<latest_release
) else (
  set LATEST=0
)

REM End the script if the script doesn't exist and we can't retrieve versions
if "%LATEST%" == "0" if "%CURRENT%" == "0" (
  echo No core script exists and the current release for download cannot be determined at this time.
  echo No action taken.
  call end
)

REM Download the newer script version if needed
if not exist %TARGETSCRIPT% set DOWNLOAD=1
if "%CURRENT%" == "0" set DOWNLOAD=1
if not "%CURRENT%" == "%LATEST%" set DOWNLOAD=1
if "%DOWNLOAD%" == "1" (
  curl -L "%DOWNLOADURL%%LATEST%/%CORESCRIPT%">%TARGETSCRIPT%
  echo %LATEST%>local_release
)

REM If a skip file exists, python won't be checked/downloaded
if exist "%BASEPATH%\skip*" goto :runScript

REM This downloads and sets up python
if exist "%PYTHONBIN%" goto :runScript
echo Downloading, installing, and updating embedded Python...
if not exist "%SMSSTEMP%" (
  md "%SMSSTEMP%"
)
curl -L %PYTHONURL% -o "%SMSSTEMP%/python.zip"
powershell Expand-Archive -Force -LiteralPath '%SMSSTEMP%/python.zip' -DestinationPath '%PYTHONDIR%'

:importSite
setlocal
>%PYTHONDIR%\%PYTHONPTH% (
    for %%I in (
        "%PYTHONZIP%"
        "."
        ""
        "import site"
    ) do echo %%~I
)

echo Setting up Python pip...
curl -L %PIPURL% -o "%SMSSTEMP%/get-pip.py"
"%PYTHONBIN%" "%SMSSTEMP%/get-pip.py" --no-warn-script-location

echo Updating pip...
"%PYTHONBIN%" -m pip install -q --upgrade pip --no-warn-script-location
echo Validating support modules...
for %%x in (bs4 colorama requests) do (
  "%PYTHONBIN%" -m pip install -q -U %%x --no-warn-script-location
)

:runScript
"%PYTHONBIN%" %CORESCRIPT%

REM If a single_run file exists exit at this time
if exist "%BASEPATH%\single_run*" goto :singleRun

goto :start

:noSpaces
echo This script cannot be run from a path having spaces.
echo     %BASEPATH%
goto :end

:singleRun
echo A file or directory starting with "single_run" exists. Remove this file to
echo allow the server to restart.
goto :end

:stopMessage
echo Remove any files or directories beginning with "stop" to allow this script to run.
dir %BASEPATH%\stop*
goto :end

:end
pause