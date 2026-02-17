# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 서버 실행 진입점 (run.py)
[v1.0.0] 개발 서버 실행. Gunicorn에서도 app 객체 직접 사용 가능.

사용법:
    python run.py                           # 개발 서버
    gunicorn --bind 0.0.0.0:8000 "run:app"  # 프로덕션 서버
"""
import os
import sys

# Windows 콘솔 인코딩 문제 방지
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("  Jissou Park Empire v0.1.0")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
