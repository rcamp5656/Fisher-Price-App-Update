@echo off
cls
set "path=c:\Fisher-Price-App"
set "bpm_temp_file=%path%\bpm.txt"

:fileone
cls
echo.
echo Select the first MIDI file for the top side of the disk.
echo You can filter the list by entering the first letter or number.
echo.
echo    - Enter a letter (e.g., 'Z') to see files starting with Z.
echo    - Enter '*' to see all MIDI files.
echo.
set /p selection1="Enter filter [0-Z or *] : "
dir %path%\Records\%selection1%*.mid /W /B
echo.
set /p UserInputFile1="Enter the first filename (without .mid extension): "

:: --- ENHANCEMENT: Check if the file exists ---
if not exist "%path%\Records\%UserInputFile1%.mid" (
    echo.
    echo ERROR: File not found! Please check the filename and try again.
    echo.
    pause
    goto fileone
)

:: DETECT BPM FOR THE FIRST MIDI FILE
echo.
echo Detecting BPM for %UserInputFile1%.mid...
%path%\src\bpm_detector.py --input %path%\Records\%UserInputFile1%.mid --output %bpm_temp_file%

:: Load BPM from the text file into a variable
set /p BPM=<"%bpm_temp_file%"
echo BPM detected: %BPM%
echo.

:: CONVERT THE FIRST MIDI FILE
echo Converting %UserInputFile1%.mid to .fpr format...
%path%\src\convert.py --input %path%\Records\%UserInputFile1%.mid --output %path%\fpr\%UserInputFile1%.fpr --bpm %BPM%
echo.
pause

:filetwo
cls
echo.
echo Select the second MIDI file for the reverse side of the disk.
echo (If creating a single-sided disk, this will be a separate file).
echo.
echo    - Enter a letter (e.g., 'Z') to see files starting with Z.
echo    - Enter '*' to see all MIDI files.
echo.
set /p selection2="Enter filter [0-Z or *] : "
dir %path%\Records\%selection2%*.mid /W /B
echo.
set /p UserInputFile2="Enter the second filename (without .mid extension): "

:: --- ENHANCEMENT: Check if the file exists ---
if not exist "%path%\Records\%UserInputFile2%.mid" (
    echo.
    echo ERROR: File not found! Please check the filename and try again.
    echo.
    pause
    goto filetwo
)

:: DETECT BPM FOR THE SECOND MIDI FILE
echo.
echo Detecting BPM for %UserInputFile2%.mid...
%path%\src\bpm_detector.py --input %path%\Records\%UserInputFile2%.mid --output %bpm_temp_file%

:: Load BPM from the text file into a variable
set /p BPM=<"%bpm_temp_file%"
echo BPM detected: %BPM%
echo.

:: CONVERT THE SECOND MIDI FILE
echo Converting %UserInputFile2%.mid to .fpr format...
%path%\src\convert.py --input %path%\Records\%UserInputFile2%.mid --output %path%\fpr\%UserInputFile2%.fpr --bpm %BPM%
echo.
pause

:create_scad
cls
set /p choice="Create a (S)ingle or (D)ouble sided disk? [S/D]: "
if /i %choice%==D goto double2
if /i %choice%==S goto single2
goto create_scad

:single2
echo Creating separate .scad files...
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile1%.fpr --scad %path%\scad\%UserInputFile1%.scad --thickness 2
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile2%.fpr --scad %path%\scad\%UserInputFile2%.scad --thickness 2
goto end

:double2
echo Creating one double-sided .scad file...
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile1%.fpr --fprverso %path%\fpr\%UserInputFile2%.fpr --scad %path%\scad\%UserInputFile1%_And_%UserInputFile2%.scad --thickness 5
goto end

:end
:: Clean up the temporary BPM file
if exist "%bpm_temp_file%" del "%bpm_temp_file%"

echo.
echo SCAD files created successfully in the '%path%\scad\' directory.
echo.
dir %path%\scad\*.scad /W /B
echo.
echo Done.
pause