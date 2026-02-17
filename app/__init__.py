# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - Flask 앱 팩토리 (__init__.py)
[v0.1.0] Flask 앱 생성, 확장 초기화, 블루프린트 등록.
"""
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from app.config import Config
from app.models import db, User

# CSRF 보호 인스턴스
csrf = CSRFProtect()


# Flask-Login 인스턴스
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '로그인이 필요한 데스! 빨리 들어오라 데스!'


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login 사용자 로드 콜백"""
    return User.query.get(int(user_id))


def create_app():
    """Flask 앱 팩토리 패턴"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # === 확장 초기화 ===
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)  # [v0.3.0] CSRF 보호 활성화

    # [v1.0.0] Phase 6: 다국어(i18n) 초기화
    from app.i18n import init_i18n
    init_i18n(app)

    # === 블루프린트 등록 ===
    from app.routes.auth_routes import auth_bp
    from app.routes.game_routes import game_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(game_bp)

    # === 루트 URL 리다이렉트 ===
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('game.dashboard'))
        return redirect(url_for('auth.login'))

    # === DB 테이블 생성 & NPC 초기화 ===
    with app.app_context():
        db.create_all()
        _init_npc_parks()

    # === 턴 스케줄러 시작 ===
    from app.turn_scheduler import init_scheduler
    init_scheduler(app)

    return app


def _init_npc_parks():
    """서버 시작 시 NPC 공원이 없으면 자동 생성"""
    from app.models import Park
    from app.config import GameConfig as GC
    import random

    # 이미 NPC가 있으면 스킵
    existing_npcs = Park.query.filter_by(is_npc=True).count()
    if existing_npcs >= GC.NPC_INITIAL_COUNT:
        return

    # NPC 공원 생성
    needed = GC.NPC_INITIAL_COUNT - existing_npcs
    available_names = [n for n in GC.NPC_PARK_NAMES
                       if not Park.query.filter_by(name=n).first()]
    random.shuffle(available_names)

    for i in range(min(needed, len(available_names))):
        personality = random.choice(GC.NPC_PERSONALITIES)
        npc = Park(
            name=available_names[i],
            is_npc=True,
            npc_personality=personality,
            boss_hp=GC.INITIAL_BOSS_HP,
            guard_count=random.randint(1, 3),
            adult_count=random.randint(3, 8),
            child_count=random.randint(5, 15),
            baby_count=random.randint(3, 10),
            konpeito=random.randint(2, 8),
            trash_food=random.randint(20, 50),
            meat_stock=random.randint(0, 5),
            material=random.randint(30, 80),
            morale=random.randint(40, 70),
            cardboard_houses=random.randint(1, 2),
            unchi_holes=random.randint(0, 2),
            walls=random.randint(0, 1),
        )
        db.session.add(npc)

    db.session.commit()
