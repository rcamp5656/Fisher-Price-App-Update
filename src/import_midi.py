@echo off
TITLE MIDI to FPR Importer

REM ##################################################################
REM # Batch file to import a MIDI file into the Music Box Tracker.   #
REM # It automatically detects the BPM and then launches the editor. #
REM #                                                                #
REM # Usage: Drag a .mid file onto this script, or run from cmd:     #
REM #   import_midi.bat "path\to\your\song.mid"                      #
REM ##################################################################

REM --- Check if a file was provided ---
if "%~1"=="" (
    echo ERROR: No MIDI file provided.
    echo.
    echo Usage: Drag a .mid file onto this batch file.
    echo.
    pause
    goto:eof
)

echo Detecting BPM for %~n1.mid...

REM --- Run the bpm_detector.py script and capture its output into the BPM variable ---
for /f %%b in ('bpm_detector.py --input "%~1"') do (
    set BPM=%%b
)

echo.
echo ----------------------------------------------------
echo   MIDI File: %~n1.mid
echo   Detected BPM: %BPM%
echo ----------------------------------------------------
echo.
echo IMPORTANT: The tracker program will now open.
echo.
echo          ###################################
echo          #  PRESS 'S' TO SAVE THE .FPR FILE  #
echo          ###################################
echo.

REM --- Launch the main tracker with the MIDI file and detected BPM ---
%SRC%\music_box_tracker.py --mid "%~1" --bpm %BPM%

echo.
echo Program finished.

:eof