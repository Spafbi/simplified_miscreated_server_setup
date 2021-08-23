@echo off
pushd "%~dp0"
set BASEPATH=%~dp0
set BASEPATH=%BASEPATH:~0,-1%
set JQURL=https://github.com/stedolan/jq/releases/download/jq-1.6/jq-win64.exe
set NSSMURL=https://nssm.cc/release/nssm-2.24.zip
set PYTHONDIR=%BASEPATH%\python
set PYTHONBIN=%PYTHONDIR%\python.exe
set SMSSTEMP=%BASEPATH%\temp
set NSSMZIP=%SMSSTEMP%\nssm-2.24.zip
set NSSMTEMPBIN=%SMSSTEMP%\nssm-2.24\win64\nssm.exe
set NSSMBIN=%BASEPATH%\nssm.exe
set JQBIN=%SMSSTEMP%\jq-win64.exe
goto :jqCheck

:jqCheck
if exist "%JQBIN%" goto :nssmCheck
echo Downloading jq...
if not exist "%SMSSTEMP%" (
  md "%SMSSTEMP%"
)
curl -L %JQURL% -o "%JQBIN%"
goto :nssmCheck

:nssmCheck
if exist "%NSSMBIN%" goto :addService
echo Downloading NSSM...
if not exist "%SMSSTEMP%" (
  md "%SMSSTEMP%"
)
curl -L %NSSMURL% -o "%NSSMZIP%"
powershell Expand-Archive -Force -LiteralPath '%NSSMZIP%' -DestinationPath '%SMSSTEMP%'
copy %NSSMTEMPBIN% %NSSMBIN%
goto :addService

:addService
FOR /F "tokens=* USEBACKQ" %%F IN (`type %BASEPATH%\smss.json ^| %JQBIN% .nt_service_name`) DO (
SET SERVICENAME=%%F
)

FOR /F "tokens=* USEBACKQ" %%F IN (`type %BASEPATH%\smss.json ^| %JQBIN% .cvars.sv_servername`) DO (
SET SERVERNAME=%%F
)

%NSSMBIN% install %SERVICENAME% %PYTHONBIN% %BASEPATH%\smss.py
%NSSMBIN% set %SERVICENAME% AppDirectory %BASEPATH%
%NSSMBIN% set %SERVICENAME% Start SERVICE_DELAYED_AUTO_START
%NSSMBIN% set %SERVICENAME% Description %SERVERNAME%
pause