@echo off
pushd "%~dp0"
set BASEPATH=%~dp0
set BASEPATH=%BASEPATH:~0,-1%

if NOT "%BASEPATH%"=="%BASEPATH: =%" goto :noSpaces

set CORESCRIPT=smss.py
set PYTHONPTH=python39._pth
set PYTHONVERSION=3.9.6
set PYTHONZIP=python39.zip

set PYTHONURL=https://www.python.org/ftp/python/%PYTHONVERSION%/python-%PYTHONVERSION%-embed-amd64.zip
set PYTHONDIR=%BASEPATH%\python
set PYTHONBIN=%PYTHONDIR%\python.exe
set PIPBIN=%PYTHONDIR%\Scripts\pip.exe
set PIPURL=https://bootstrap.pypa.io/get-pip.py
set SMSSTEMP=%BASEPATH%\temp
if exist "%BASEPATH%\skip" goto :runScript
if exist "%BASEPATH%\skip.txt" goto :runScript
goto :pythonCheck

:pythonCheck
if exist "%PYTHONBIN%" goto :importSite
echo Downloading, installing, and updating embedded Python...
if not exist "%SMSSTEMP%" (
  md "%SMSSTEMP%"
)
curl -L %PYTHONURL% -o "%SMSSTEMP%/python.zip"
powershell Expand-Archive -Force -LiteralPath '%SMSSTEMP%/python.zip' -DestinationPath '%PYTHONDIR%'
goto :importSite

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
goto :pipCheck

:pipCheck
echo Setting up Python pip...
curl -L %PIPURL% -o "%SMSSTEMP%/get-pip.py"
"%PYTHONBIN%" "%SMSSTEMP%/get-pip.py" --no-warn-script-location
goto :moduleCheck

:moduleCheck
echo Updating pip...
"%PYTHONBIN%" -m pip install -q --upgrade pip --no-warn-script-location
echo Validating support modules...
for %%x in (bs4 colorama requests) do (
  "%PYTHONBIN%" -m pip install -q -U %%x --no-warn-script-location
)
goto :runScript

:runScript
"%PYTHONBIN%" %CORESCRIPT%
goto :end

:noSpaces
echo This script cannot be run from a path having spaces.
echo     %BASEPATH%
goto :end

:end
pause