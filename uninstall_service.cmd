@echo off
pushd "%~dp0"
set BASEPATH=%~dp0
set BASEPATH=%BASEPATH:~0,-1%
set JQURL=https://github.com/stedolan/jq/releases/download/jq-1.6/jq-win64.exe
set SMSSTEMP=%BASEPATH%\temp
set JQBIN=%SMSSTEMP%\jq-win64.exe
goto :jqCheck

:jqCheck
if exist "%JQBIN%" goto :addService
echo Downloading jq...
if not exist "%SMSSTEMP%" (
  md "%SMSSTEMP%"
)
curl -L %JQURL% -o "%JQBIN%"
goto :addService

:addService
FOR /F "tokens=* USEBACKQ" %%F IN (`type %BASEPATH%\smss.json ^| %JQBIN% .nt_service_name`) DO (
SET SERVICENAME=%%F
)
ECHO %SERVICENAME%

sc delete %SERVICENAME%
pause