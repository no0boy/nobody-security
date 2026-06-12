@echo off
cd /d C:\Users\syc\Desktop\ai-nobody
REM 下面改成你的管理员密码
set ADMIN_KEY=你的密码
start http://localhost:8000/app/login.html
uvicorn main:app --host 0.0.0.0 --port 8000
