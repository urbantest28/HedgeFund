Dim shell, pid, pidFile, fso
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

pidFile = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\") - 1) & "\logs\server.pid"

If fso.FileExists(pidFile) Then
    Dim f
    Set f = fso.OpenTextFile(pidFile, 1)
    pid = Trim(f.ReadAll())
    f.Close
    shell.Run "taskkill /PID " & pid & " /F", 0, True
    fso.DeleteFile pidFile
    MsgBox "HedgeFund server stopped.", 64, "HedgeFund"
Else
    MsgBox "Server does not appear to be running.", 64, "HedgeFund"
End If
