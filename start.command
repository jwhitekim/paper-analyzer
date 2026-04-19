#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "가상환경 생성 중..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo "서버 시작: http://localhost:8000"
open http://localhost:8000
python main.py
