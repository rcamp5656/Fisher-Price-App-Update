@echo off


cls
set path=c:\Fisher-Price-App
;
;
:midi
; 

:twoonly
echo ;
:fileone
cls
echo You now have a choice of only group of files ie: 0 would return all files starting with 0.
echo                                                  Z would return all files starting with Z.
echo                                                  * would return all files in the midi directory.
echo ;
set /p selection1=Enter just one letter from [0 to Z  or *] : 
dir %path%\Records\%selection1%*.mid /W
echo ;
set /p UserInputFile1=Please enter the first filename  [Without Extender] 

:first3
set UserTempo1=120
copy %path%\Records\%UserInputFile1%.mid %path%\temp\%UserInputFile1%.mid
copy %path%\Records\%UserInputFile1%.mid %path%\fpr\%UserInputFile1%.mid
%path%\src\music_box_tracker.py --mid %path%\temp\%UserInputFile1%.mid --audio midi --title %UserInputFile1%
set /p YesNo1=Did that song work out and do you want to select a new file for %UserInputFile1%  [Y] [N] : 
if %YesNo1%==Y goto fileone
if %YesNo1%==y goto fileone
echo ;%
:filetwo
cls
echo You now have a choice of only group of files ie: 0 would return all files starting with 0.
echo                                                  Z would return all files starting with Z.
echo                                                  * would return all files in the midi directory.
echo ;
set /p selection2=Enter just one letter from [0 to Z  or *] : 
dir %path%\Records\%selection2%*.mid /W
set /p UserInputFile2=Please enter the second filename [Without Extender] 
:second3
copy %path%\Records\%UserInputFile2%.mid %path%\temp\%UserInputFile2%.mid
copy %path%\Records\%UserInputFile2%.mid %path%\fpr\%UserInputFile2%.mid
set UserTempo2=120
%path%\src\music_box_tracker.py --mid %path%\temp\%UserInputFile2%.mid --audio midi --title %UserInputFile2%
set /p YesNo2=Did that song work out and do you want to select a new file for %UserInputFile2% [Y] or [N] : 
if %YesNo2%==Y goto filetwo
if %YesNo2%==y goto filetwo
echo ;
copy %path%\temp\%UserInputFile1%.fpr %path%\fpr\%UserInputFile1%.fpr
copy %path%\temp\%UserInputFile2%.fpr %path%\fpr\%UserInputFile2%.fpr
echo ;
set /p choice=You can create Single or Double Sided Disks [S] [D] : 
if %choice%==D goto double2
if %choice%==d goto double2
if %choice%==S goto single2
if %choice%==s goto single2
:single2
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile1%.fpr --scad %path%\scad\%UserInputFile1%.scad --thickness 3
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile2%.fpr --scad %path%\scad\%UserInputFile2%.scad --thickness 3
goto eraseit
:double2
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile1%.fpr --fprverso %path%\fpr\%UserInputFile2%.fpr --scad %path%\scad\%UserInputFile1%_And_%UserInputFile2%.scad --thickness 5

:fprselect
echo ;
set /p choice=Single or Double Sided Disks [S] [D] : 
if %choice%==D goto double
if %choice%==d goto double
if %choice%==S goto single
if %choice%==s goto single
;
:single
echo creating Single Sided Scad Files...
echo ;
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile1%.fpr --scad %path%\scad\%UserInputFile1%.scad --thickness 2
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile2%.fpr --scad %path%\scad\%UserInputFile2%.scad --thickness 2
echo ;
goto eraseit
echo creating Double Sided Scad Files...
:double
echo ;
%path%\src\fpr_to_scad.py --fpr %path%\fpr\%UserInputFile1%.fpr --fprverso %path%\fpr\%UserInputFile2%.fpr --scad %path%\scad\%UserInputFile1%_And_%UserInputFile2%.scad --thickness 5
echo ;
echo ;
:eraseit
erase %path%\midi\*.fpr
erase %path%\temp\*.*
echo ;
dir %path%\scad\*.scad /W
echo Done
;
pause
