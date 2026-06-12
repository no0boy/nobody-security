Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' 改成你的密码
adminKey = "你的密码"

' 静默启动 uvicorn
WshShell.Environment("Process")("ADMIN_KEY") = adminKey
WshShell.CurrentDirectory = dir
WshShell.Run "cmd /c uvicorn main:app --host 0.0.0.0 --port 8000", 0, False

' 等 3 秒后打开浏览器
WScript.Sleep 3000
WshShell.Run "http://localhost:8000/app/login.html"
