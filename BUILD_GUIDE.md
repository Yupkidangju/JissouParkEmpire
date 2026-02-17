# 빌드 & 배포 가이드 (BUILD_GUIDE.md)

## 빠른 시작 (로컬 개발)

### 1. 사전 요구사항
- Python 3.9 이상
- pip (Python 패키지 관리자)

### 2. 설치 & 실행

```bash
# 저장소 클론
git clone <your-repo-url>
cd JissouParkEmpire

# 가상환경 생성 및 활성화
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python run.py
```

3. 브라우저에서 `http://localhost:5000` 접속

---

## 라즈베리파이 배포 가이드

### 1. 환경 준비

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python3 및 pip 설치 확인
sudo apt install -y python3 python3-pip python3-venv

# 프로젝트 디렉토리 생성
sudo mkdir -p /opt/jissou-park
sudo chown $USER:$USER /opt/jissou-park
```

### 2. 프로젝트 배포

```bash
# 프로젝트 복사 (scp 또는 git clone)
cd /opt/jissou-park
git clone <your-repo-url> .

# 가상환경 생성 및 의존성 설치
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Gunicorn 설치 (프로덕션 WSGI 서버)
pip install gunicorn
```

### 3. 환경 변수 설정

```bash
# .env 파일 생성 (직접 생성해야 함)
cat > /opt/jissou-park/.env << 'EOF'
FLASK_ENV=production
SECRET_KEY=여기에_랜덤_시크릿키_입력_데스
TURN_INTERVAL=600
EOF
```

> **중요**: `SECRET_KEY`는 `python3 -c "import secrets; print(secrets.token_hex(32))"` 로 생성하세요.

### 4. systemd 서비스 등록

```bash
# 서비스 파일 생성
sudo tee /etc/systemd/system/jissou-park.service << 'EOF'
[Unit]
Description=Jissou Park Empire - 실장석 공원 제국
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/jissou-park
Environment="PATH=/opt/jissou-park/venv/bin"
ExecStart=/opt/jissou-park/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /opt/jissou-park/logs/access.log \
    --error-logfile /opt/jissou-park/logs/error.log \
    "run:app"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

```bash
# 로그 디렉토리 생성
mkdir -p /opt/jissou-park/logs

# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable jissou-park
sudo systemctl start jissou-park

# 상태 확인
sudo systemctl status jissou-park
```

#### Gunicorn에 맞게 run.py 수정 필요

```python
# run.py 끝에 추가 (Gunicorn이 app 객체를 인식하도록)
app = create_app()
```

### 5. Nginx 리버스 프록시 설정

```bash
# Nginx 설치
sudo apt install -y nginx

# 사이트 설정 파일 생성
sudo tee /etc/nginx/sites-available/jissou-park << 'EOF'
server {
    listen 80;
    server_name _;  # 또는 실제 도메인명

    # 정적 파일 직접 서빙 (성능 향상)
    location /static/ {
        alias /opt/jissou-park/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 애플리케이션 프록시
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 지원 (향후 실시간 기능용)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 타임아웃 설정
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF
```

```bash
# 사이트 활성화
sudo ln -sf /etc/nginx/sites-available/jissou-park /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Nginx 설정 검증 및 재시작
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 6. 방화벽 설정

```bash
# ufw 사용 시
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

---

## 운영 명령어

```bash
# 서비스 상태 확인
sudo systemctl status jissou-park

# 서비스 재시작
sudo systemctl restart jissou-park

# 로그 확인
journalctl -u jissou-park -f
tail -f /opt/jissou-park/logs/access.log
tail -f /opt/jissou-park/logs/error.log

# 코드 업데이트 후 재배포
cd /opt/jissou-park
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart jissou-park
```

---

## 성능 최적화 (라즈베리파이)

| 항목 | 설정 | 설명 |
|------|------|------|
| **Gunicorn Workers** | 2 | RPi는 코어 수가 적으므로 2개 권장 |
| **SQLite WAL 모드** | 자동 적용 | 동시 읽기 성능 향상 |
| **정적 파일** | Nginx 직접 서빙 | Gunicorn 부하 감소 |
| **턴 간격** | 600초 (10분) | CPU 부하 분산 |
| **DB 백업** | `cp instance/game.db backup/` | 주기적 백업 권장 |

---

## 트러블슈팅

### 서비스가 시작되지 않을 때
```bash
journalctl -u jissou-park --no-pager -n 50
```

### DB 파일 권한 문제
```bash
sudo chown pi:pi /opt/jissou-park/instance/game.db
chmod 664 /opt/jissou-park/instance/game.db
```

### 포트 충돌
```bash
sudo lsof -i :8000
sudo lsof -i :80
```

---

## 안드로이드 APK 빌드 (추후 개발)

> **상태**: Phase 9 — 추후 개발 예정

### 빌드 방식: Kivy/BeeWare (Python 네이티브)

```
[재사용 대상 — 변경 없이 이식]
  game_engine.py    (1200줄) → 행동/턴/자원 로직
  battle_engine.py  (240줄)  → 전투 시뮬레이션
  npc_engine.py     (140줄)  → NPC AI 5종
  dialogues.py      (620줄)  → 대사 시스템
  config.py         (240줄)  → 밸런스 상수
  models.py         (340줄)  → SQLAlchemy ORM (SQLite)
  lang/*.json       (258키×5) → 다국어

[재작성 대상]
  UI 계층           → Kivy 위젯 (레트로 터미널 감성)
  인증 계층         → 제거 (로컬 싱글 프로필)
  교역/외교         → NPC 자동화

[도구]
  Buildozer         → Kivy APK 빌드 자동화
  python-for-android → Android용 Python 패키징
```

### 솔플 전환 변경점

| 현재 (웹 멀티) | APK (솔플) |
|---------------|-----------|
| Flask 라우트 기반 | Kivy Screen 기반 |
| User 인증 (로그인/가입) | 로컬 프로필 (자동 시작) |
| 교역 (플레이어 간) | NPC 자동교역 |
| 외교 (동맹/적대 요청) | NPC 자동외교 |
| 랭킹 (플레이어 포함) | NPC끼리 랭킹 |
| APScheduler (서버 턴) | 로컬 타이머 (온디맨드) |
| 브라우저 UI | Kivy 네이티브 UI |

### 예상 스펙

| 항목 | 값 |
|------|-------------|
| APK 크기 | ~30~50MB (Python 런타임 포함) |
| 최소 Android | 5.0 (API 21) |
| 스토어 | Google Play (무료) |
| 타겟 | 일본/중국/한국 실장석 팬층 |
| 개발 기간 | 1~2주 (UI 재작성) |

