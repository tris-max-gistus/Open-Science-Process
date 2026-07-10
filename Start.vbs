' Launches the AI Usage Logger with no visible console window.
' Double-click this file (or a shortcut to it) to start the app silently;
' your browser will open once it's ready. If something goes wrong, a
' small error window will appear and details are saved to launch_log.txt
' in the app folder. Use app\start.bat instead if you need to see setup output.

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strPath
objShell.Run "pythonw """ & strPath & "\app\start.py""", 0, False
