Option Explicit
Dim sh, fs, folder, py, q, cfg
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)
If Not fs.FileExists(folder & "\resident-python.txt") Then WScript.Quit 1
Set cfg = fs.OpenTextFile(folder & "\resident-python.txt", 1, False, -1)
py = cfg.ReadLine: cfg.Close
If Not fs.FileExists(py) Then WScript.Quit 1
sh.Environment("PROCESS").Remove "PYTHONHOME"
sh.Environment("PROCESS").Remove "PYTHONPATH"
sh.CurrentDirectory = folder
sh.Run q & py & q & " " & q & folder & "\run_tracker.pyw" & q & " --resident --background", 0, False
