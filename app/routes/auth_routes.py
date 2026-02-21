# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 인증 라우트 (auth_routes.py)
[v0.1.0] 회원가입, 로그인, 로그아웃 처리.
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.models import db, User, Park
from app.config import GameConfig as GC
from app.i18n import get_text

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """루트 경로 - 로그인 여부에 따라 분기"""
    if current_user.is_authenticated:
        return redirect(url_for('game.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 처리"""
    if current_user.is_authenticated:
        return redirect(url_for('game.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash(get_text('flash.auth_empty'), 'error')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            # 로그인 성공
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=True)
            flash(get_text('flash.auth_welcome'), 'success')
            return redirect(url_for('game.dashboard'))
        else:
            flash(get_text('flash.auth_invalid'), 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """회원가입 + 공원 자동 생성"""
    if current_user.is_authenticated:
        return redirect(url_for('game.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        park_name = request.form.get('park_name', '').strip()

        # 입력 검증
        if not username or not password or not park_name:
            flash(get_text('flash.reg_empty'), 'error')
            return render_template('register.html')

        if len(username) < 2 or len(username) > 20:
            flash(get_text('flash.reg_username_len'), 'error')
            return render_template('register.html')

        if len(password) < 4:
            flash(get_text('flash.reg_password_short'), 'error')
            return render_template('register.html')

        if password != password2:
            flash(get_text('flash.reg_password_mismatch'), 'error')
            return render_template('register.html')

        if len(park_name) < 2 or len(park_name) > 30:
            flash(get_text('flash.reg_parkname_len'), 'error')
            return render_template('register.html')

        # [v1.5.0] XSS 방지: 아이디/공원 이름에 HTML 특수문자 차단
        import re
        _DANGEROUS_CHARS = re.compile(r'[<>&\"\'/\\]')
        if _DANGEROUS_CHARS.search(username):
            flash(get_text('flash.reg_invalid_chars'), 'error')
            return render_template('register.html')
        if _DANGEROUS_CHARS.search(park_name):
            flash(get_text('flash.reg_invalid_chars'), 'error')
            return render_template('register.html')

        # 중복 확인
        if User.query.filter_by(username=username).first():
            flash(get_text('flash.reg_username_dup'), 'error')
            return render_template('register.html')

        if Park.query.filter_by(name=park_name).first():
            flash(get_text('flash.reg_parkname_dup'), 'error')
            return render_template('register.html')

        # 사용자 생성
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # user.id 확보

        # 공원 생성 (초기 자원 설정)
        park = Park(
            user_id=user.id,
            name=park_name,
            is_npc=False,
            boss_hp=GC.INITIAL_BOSS_HP,
            guard_count=GC.INITIAL_GUARDS,
            adult_count=GC.INITIAL_ADULTS,
            child_count=GC.INITIAL_CHILDREN,
            baby_count=GC.INITIAL_BABIES,
            konpeito=GC.INITIAL_KONPEITO,
            trash_food=GC.INITIAL_TRASH_FOOD,
            meat_stock=GC.INITIAL_MEAT_STOCK,
            material=GC.INITIAL_MATERIAL,
            konpeito_cap=GC.INITIAL_KONPEITO_CAP,
            trash_food_cap=GC.INITIAL_TRASH_FOOD_CAP,
            material_cap=GC.INITIAL_MATERIAL_CAP,
            population_cap=GC.INITIAL_POP_CAP,
            morale=GC.INITIAL_MORALE,
            action_points=GC.ACTION_POINTS_PER_TURN,
        )
        db.session.add(park)
        db.session.commit()

        # 자동 로그인
        login_user(user, remember=True)
        flash(get_text('flash.reg_success', name=park_name), 'success')
        return redirect(url_for('game.dashboard'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """로그아웃"""
    logout_user()
    flash(get_text('flash.auth_logout'), 'info')
    return redirect(url_for('auth.login'))
