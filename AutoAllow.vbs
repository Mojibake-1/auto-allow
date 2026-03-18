Set WshShell = CreateObject("WScript.Shell")
strPath = Replace(WScript.ScriptFullName, WScript.ScriptName, "")
WshShell.Run "pythonw """ & strPath & "auto_allow.py""", 0, False
