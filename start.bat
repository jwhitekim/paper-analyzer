@echo off
cd /d "%~dp0"

if not exist "venv" (
  echo 가상환경 생성 중...
  python -m venv venv
)

call venv\Scripts\activate
pip install -q -r requirements.txt

start http://localhost:8000
python main.py
pause
