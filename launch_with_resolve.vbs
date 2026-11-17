Option Explicit
Dim sh, fs, folder, py, cfg, q, ignored
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)
If Not fs.FileExists(folder & "\launcher-config.txt") Then
 MsgBox "Run REPAIR-LINKED.bat first.",48,"Stintory": WScript.Quit 1
End If
Set cfg = fs.OpenTextFile(folder & "\launcher-config.txt", 1, False, -1)
ignored = cfg.ReadLine: py = cfg.ReadLine: cfg.Close
If Not fs.FileExists(py) Then
 MsgBox "Python moved. Run REPAIR-LINKED.bat again.",48,"Stintory": WScript.Quit 1
End If
On Error Resume Next
sh.Environment("PROCESS").Remove "PYTHONHOME"
sh.Environment("PROCESS").Remove "PYTHONPATH"
On Error GoTo 0
sh.CurrentDirectory = folder
sh.Run q & py & q & " " & q & folder & "\launch_resolve.pyw" & q, 0, False
