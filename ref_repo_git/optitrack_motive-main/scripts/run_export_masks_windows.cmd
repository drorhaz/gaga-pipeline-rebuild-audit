@echo off
setlocal

set "PATH=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Redist\MSVC\14.44.35112\x64\Microsoft.VC143.CRT;C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Redist\MSVC\14.44.35112\x64\Microsoft.VC143.OpenMP;C:\Program Files\OptiTrack\Motive\lib;C:\Program Files\OptiTrack\Motive;C:\Program Files\OptiTrack\Motive\plugins;%PATH%"
set "QT_PLUGIN_PATH=C:\Program Files\OptiTrack\Motive\plugins"
set "QT_QPA_PLATFORM_PLUGIN_PATH=C:\Program Files\OptiTrack\Motive\plugins\platforms"
set "CALIB_PATH=C:\ProgramData\OptiTrack\Motive\System Calibration.mcal"
set "OUT_DIR=C:\tmp\mask_export_exact"
set "LOG_PATH=%OUT_DIR%\run.log"

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

"C:\tmp\export_masks_windows.exe" "%CALIB_PATH%" "%OUT_DIR%" > "%LOG_PATH%" 2>&1
echo exitcode=%ERRORLEVEL%>> "%LOG_PATH%"
exit /b %ERRORLEVEL%
