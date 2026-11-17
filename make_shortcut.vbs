Option Explicit
Dim sh, fs, folder, lnk
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
Set lnk = sh.CreateShortcut(sh.SpecialFolders("Desktop") & "\Stintory.lnk")
lnk.TargetPath = folder & "\run.bat"
lnk.WorkingDirectory = folder
lnk.Description = "Open Stintory time tracker"
lnk.IconLocation = folder & "\app.ico,0"
lnk.WindowStyle = 7
lnk.Save
