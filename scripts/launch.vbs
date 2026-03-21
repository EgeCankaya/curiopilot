Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "F:\Coding\curiopilot"
WshShell.Run Chr(34) & "F:\Coding\curiopilot\scripts\launch.bat" & Chr(34), 0, False
