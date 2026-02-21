# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 게임 라우트 (game_routes.py)
[v0.1.0] 대시보드, 채집, 건설, 출산, 솎아내기, 훈련 등 게임 행동 처리.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.models import db, Park, EventLog
from app.config import GameConfig as GC
from app import game_engine
from app import dialogues as DLG
from app.i18n import get_text

game_bp = Blueprint('game', __name__, url_prefix='/game')


@game_bp.route('/dashboard')
@login_required
def dashboard():
    """메인 대시보드 - 공원 현황 표시"""
    park = current_user.park
    if not park:
        flash(get_text('flash.no_park'), 'error')
        return redirect(url_for('auth.login'))

    if park.is_destroyed:
        return render_template('gameover.html', park=park)

    # [v1.2.0] 접속 시 턴 자동 충전
    charged = game_engine.recharge_turns(park)
    if charged > 0:
        flash(f'⚡ {charged}턴 충전 완료! (현재 {park.turn_quota}/{GC.TURN_QUOTA_MAX})', 'info')

    # [v1.3.0] 보호 모드 체크 + 자원 리셋
    protection_reset = game_engine.check_and_enter_protection(park)
    if protection_reset:
        flash(get_text('flash.protect_activated'), 'info')

    # [v1.2.0] 턴 정보
    turn_info = game_engine.get_turn_info(park)

    # [v1.3.0] 보호 모드 정보
    protect_info = game_engine.get_protection_info(park)

    # 최근 이벤트 로그 (최신 10개)
    recent_logs = EventLog.query.filter_by(park_id=park.id) \
        .order_by(EventLog.created_at.desc()).limit(10).all()

    # 건설/훈련 대기열
    building_queue = park.build_queue
    training_queue = park.train_queue

    # 인사말
    greeting = DLG.get_random_dialogue(DLG.DASHBOARD_GREETING)

    # NPC 공원 목록 (전투/정찰용)
    other_parks = Park.query.filter(
        Park.id != park.id,
        Park.is_destroyed == False
    ).all()

    return render_template('dashboard.html',
                           park=park,
                           turn_info=turn_info,
                           protect_info=protect_info,
                           recent_logs=recent_logs,
                           building_queue=building_queue,
                           training_queue=training_queue,
                           greeting=greeting,
                           other_parks=other_parks,
                           buildings=GC.BUILDINGS,
                           GC=GC)


@game_bp.route('/gather', methods=['POST'])
@login_required
def gather():
    """채집 행동 실행 [v1.2.0] 턴 1개 소비"""
    park = current_user.park

    # [v1.2.0] 턴 소비 + 턴 처리
    turn_ok, turn_msgs = game_engine.consume_turn(park)
    if not turn_ok:
        for msg in turn_msgs:
            flash(msg, 'error')
        return redirect(url_for('game.dashboard'))

    num_adults = int(request.form.get('num_adults', 0))
    num_children = int(request.form.get('num_children', 0))

    success, result, messages = game_engine.action_gather(
        park, num_adults, num_children
    )

    for msg in messages:
        flash(msg, 'success' if success else 'error')

    if success:
        flash(f"🌿 수확: 🗑️음쓰 +{result['trash']} "
              f"🍬콘페이토 +{result['konpeito']} "
              f"🧱자재 +{result['material']}", 'info')

    return redirect(url_for('game.dashboard'))


@game_bp.route('/cull', methods=['POST'])
@login_required
def cull():
    """솎아내기 (도살) 행동"""
    park = current_user.park
    target = request.form.get('target_type', '')  # 'baby' 또는 'child'
    convert = request.form.get('convert_to', '')  # 'food' 또는 'material'
    count = int(request.form.get('count', 1))

    success, result, messages = game_engine.action_cull(
        park, target, convert, count
    )

    for msg in messages:
        flash(msg, 'warning' if success else 'error')

    return redirect(url_for('game.dashboard'))


@game_bp.route('/birth', methods=['POST'])
@login_required
def birth():
    """출산 행동 [v1.2.0] 턴 1개 소비"""
    park = current_user.park

    # [v1.2.0] 턴 소비
    turn_ok, turn_msgs = game_engine.consume_turn(park)
    if not turn_ok:
        for msg in turn_msgs:
            flash(msg, 'error')
        return redirect(url_for('game.dashboard'))

    success, result, messages = game_engine.action_birth(park)

    for msg in messages:
        flash(msg, 'success' if success else 'error')

    if success:
        flash(f"🐣 태어남: 👶자실장 +{result['children']}, "
              f"🐛저실장 +{result['babies']}", 'info')

    return redirect(url_for('game.dashboard'))


@game_bp.route('/build', methods=['POST'])
@login_required
def build():
    """건설 행동 [v1.2.0] 턴 1개 소비"""
    park = current_user.park
    building_type = request.form.get('building_type', '')

    # [v1.2.0] 턴 소비
    turn_ok, turn_msgs = game_engine.consume_turn(park)
    if not turn_ok:
        for msg in turn_msgs:
            flash(msg, 'error')
        return redirect(url_for('game.dashboard'))

    success, result, messages = game_engine.action_build(park, building_type)

    for msg in messages:
        flash(msg, 'success' if success else 'error')

    return redirect(url_for('game.dashboard'))


@game_bp.route('/train', methods=['POST'])
@login_required
def train():
    """훈련 행동 [v1.2.0] 턴 1개 소비"""
    park = current_user.park

    # [v1.2.0] 턴 소비
    turn_ok, turn_msgs = game_engine.consume_turn(park)
    if not turn_ok:
        for msg in turn_msgs:
            flash(msg, 'error')
        return redirect(url_for('game.dashboard'))

    success, result, messages = game_engine.action_train(park)

    for msg in messages:
        flash(msg, 'success' if success else 'error')

    return redirect(url_for('game.dashboard'))


@game_bp.route('/attack', methods=['POST'])
@login_required
def attack():
    """침공 행동 [v1.2.0] 턴 1개 소비 [v0.4.0] 동맹 차단 + 적대 약탈 보너스"""
    park = current_user.park

    # [v1.2.0] 턴 소비
    turn_ok, turn_msgs = game_engine.consume_turn(park)
    if not turn_ok:
        for msg in turn_msgs:
            flash(msg, 'error')
        return redirect(url_for('game.dashboard'))

    # [v1.3.0] 보호 모드 - 자기가 보호 중이면 침공 불가
    if game_engine.is_protected(park):
        flash(f'🛡️ 보호 모드 중에는 침공할 수 없는 데스! '
              f'(경호 {GC.PROTECT_GUARD_MIN}↑ & 성체 {GC.PROTECT_ADULT_MIN}↑ 필요)', 'error')
        return redirect(url_for('game.dashboard'))

    target_id = int(request.form.get('target_id', 0))
    send_guards = int(request.form.get('send_guards', 0))
    send_adults = int(request.form.get('send_adults', 0))
    boss_joins = request.form.get('boss_joins') == 'on'

    if park.action_points < 2:
        flash(get_text('flash.ap_attack_need'), 'error')
        return redirect(url_for('game.dashboard'))

    target = Park.query.get(target_id)
    if not target or target.is_destroyed or target.id == park.id:
        flash(get_text('flash.invalid_target'), 'error')
        return redirect(url_for('game.dashboard'))

    # [v1.3.0] 보호 모드 - 보호 대상 침공 불가
    if game_engine.is_protected(target):
        flash(get_text('flash.protect_target', name=target.name), 'error')
        return redirect(url_for('game.dashboard'))

    # [v0.4.0] 동맹 차단: 동맹인 상대는 침공 불가
    from app.models import Diplomacy
    is_ally = Diplomacy.query.filter(
        ((Diplomacy.park_a_id == park.id) & (Diplomacy.park_b_id == target.id)) |
        ((Diplomacy.park_a_id == target.id) & (Diplomacy.park_b_id == park.id)),
        Diplomacy.relation_type == 'ally',
        Diplomacy.status == 'active'
    ).first()
    if is_ally:
        flash(get_text('flash.ally_no_attack', name=target.name), 'error')
        return redirect(url_for('game.dashboard'))

    # 출정 인원 검증
    if send_guards + send_adults == 0 and not boss_joins:
        flash(get_text('flash.attack_min_unit'), 'error')
        return redirect(url_for('game.dashboard'))

    # AP 소비
    park.action_points -= 2

    from app.battle_engine import execute_battle
    won, loot, messages = execute_battle(park, target,
                                          send_guards=send_guards,
                                          send_adults=send_adults,
                                          boss_joins=boss_joins)

    # [v0.4.0] 적대 보너스: 적대 관계면 약탈 +20%
    if won:
        is_enemy = Diplomacy.query.filter(
            ((Diplomacy.park_a_id == park.id) & (Diplomacy.park_b_id == target.id)) |
            ((Diplomacy.park_a_id == target.id) & (Diplomacy.park_b_id == park.id)),
            Diplomacy.relation_type == 'enemy',
            Diplomacy.status == 'active'
        ).first()
        if is_enemy:
            # 약탈 20% 추가 보너스
            bonus_k = int(loot['konpeito'] * 0.2)
            bonus_t = int(loot['trash'] * 0.2)
            bonus_m = int(loot['material'] * 0.2)
            loot['konpeito'] += bonus_k
            loot['trash'] += bonus_t
            loot['material'] += bonus_m
            # 보너스분 실제 적용
            park.konpeito = min(park.konpeito + bonus_k, park.konpeito_cap)
            park.trash_food = min(park.trash_food + bonus_t, park.trash_food_cap)
            park.material = min(park.material + bonus_m, park.material_cap)
            target.konpeito = max(0, target.konpeito - bonus_k)
            target.trash_food = max(0, target.trash_food - bonus_t)
            target.material = max(0, target.material - bonus_m)
            db.session.commit()
            messages.append(get_text('flash.enemy_bonus', k=bonus_k, t=bonus_t, m=bonus_m))

    for msg in messages:
        if won:
            flash(msg, 'success')
        else:
            flash(msg, 'warning')

    if won:
        flash(get_text('flash.attack_win', konpeito=loot['konpeito'], trash=loot['trash'],
              material=loot['material'], babies=loot['babies'], children=loot['children']), 'info')

    return redirect(url_for('game.dashboard'))


@game_bp.route('/defend', methods=['POST'])
@login_required
def defend():
    """방어 배치 행동 (1 AP)"""
    park = current_user.park
    num_guards = int(request.form.get('num_guards', 0))
    num_adults = int(request.form.get('num_adults', 0))

    if park.action_points < 1:
        flash(get_text('flash.ap_insufficient'), 'error')
        return redirect(url_for('game.dashboard'))

    if num_guards > park.guard_count or num_adults > park.adult_count:
        flash(get_text('flash.defend_insufficient'), 'error')
        return redirect(url_for('game.dashboard'))

    park.action_points -= 1
    park.defending_guards = num_guards
    park.defending_adults = num_adults
    db.session.commit()

    flash(get_text('flash.defend_deploy', guards=num_guards, adults=num_adults), 'success')
    return redirect(url_for('game.dashboard'))


@game_bp.route('/battle-logs')
@login_required
def battle_logs():
    """전투 기록 조회"""
    park = current_user.park
    from app.models import BattleLog

    logs = BattleLog.query.filter(
        db.or_(BattleLog.attacker_id == park.id, BattleLog.defender_id == park.id)
    ).order_by(BattleLog.created_at.desc()).limit(20).all()

    return render_template('battle_logs.html', park=park, logs=logs)


@game_bp.route('/debug/next-turn', methods=['POST'])
@login_required
def debug_next_turn():
    """디버그: 턴 강제 실행 (개발 편의용)"""
    from flask import current_app
    from app.turn_scheduler import force_process_turn

    park = current_user.park
    force_process_turn(current_app._get_current_object(), park.id)
    flash(get_text('flash.debug_turn', turn=park.turn_count), 'info')
    return redirect(url_for('game.dashboard'))


@game_bp.route('/restart', methods=['POST'])
@login_required
def restart():
    """게임오버 후 재시작 - 멸망한 공원을 삭제하고 새 공원 생성"""
    park = current_user.park

    if not park or not park.is_destroyed:
        flash(get_text('flash.restart_not_destroyed'), 'warning')
        return redirect(url_for('game.dashboard'))

    # 기존 공원의 정보 보존
    old_name = park.name

    # 기존 공원 삭제 (cascade로 큐/이벤트 같이 삭제됨)
    db.session.delete(park)
    db.session.commit()

    # 새 공원 생성 (Park 모델의 default 값이 자동 적용됨)
    new_park = Park(
        user_id=current_user.id,
        name=f"{current_user.username}의 공원",
    )
    db.session.add(new_park)
    db.session.commit()

    flash(get_text('flash.restart_success', name=old_name), 'success')
    return redirect(url_for('game.dashboard'))


@game_bp.route('/api/park-status')
@login_required
def park_status():
    """AJAX 공원 상태 조회 API"""
    park = current_user.park
    if not park:
        return jsonify({'error': get_text('flash.no_park')}), 404
    return jsonify(park.to_dict())


# ============================================================
# [v0.4.0] Phase 5: 실시간 알림 API
# ============================================================

@game_bp.route('/api/notifications')
@login_required
def notifications():
    """
    알림 API - 최근 이벤트 중 중요 알림(침공, 교역, 외교) 반환.
    클라이언트가 last_id를 전달하면 그 이후의 알림만 반환.
    """
    park = current_user.park
    if not park:
        return jsonify({'notifications': []})

    last_id = request.args.get('last_id', 0, type=int)

    # 중요 이벤트 타입만 필터 (battle, trade, diplomacy)
    important_types = ['battle', 'trade', 'diplomacy']
    events = EventLog.query.filter(
        EventLog.park_id == park.id,
        EventLog.id > last_id,
        EventLog.event_type.in_(important_types)
    ).order_by(EventLog.id.asc()).limit(10).all()

    notifications = []
    for evt in events:
        notifications.append({
            'id': evt.id,
            'type': evt.event_type,
            'message': evt.message,
            'turn': evt.turn_number,
        })

    return jsonify({'notifications': notifications})


@game_bp.route('/ranking')
@login_required
def ranking():
    """랭킹 페이지 - 전투력/인구/승수/자원 순위"""
    from app.models import BattleLog
    from sqlalchemy import func

    park = current_user.park
    sort_by = request.args.get('sort', 'power')

    # 정렬 기준별 라벨
    sort_labels = {
        'power': '⚔️ 전투력',
        'population': '👥 인구',
        'wins': '🏆 승수',
        'resources': '💰 자원'
    }
    sort_label = sort_labels.get(sort_by, '⚔️ 전투력')

    # 모든 비멸망 공원 조회
    all_parks = Park.query.filter_by(is_destroyed=False).all()

    # 각 공원의 승/패 수 계산
    win_counts = {}
    loss_counts = {}
    for p in all_parks:
        wins = BattleLog.query.filter_by(attacker_id=p.id, result='win').count()
        wins += BattleLog.query.filter_by(defender_id=p.id, result='lose').count()
        losses = BattleLog.query.filter_by(attacker_id=p.id, result='lose').count()
        losses += BattleLog.query.filter_by(defender_id=p.id, result='win').count()
        win_counts[p.id] = wins
        loss_counts[p.id] = losses

    # NPC 성격 이모지
    personality_emojis = {
        'aggressive': '🗡️',
        'defensive': '🛡️',
        'peaceful': '🌿',
        'cunning': '🎭',
        'berserk': '💀',
    }

    # 랭킹 데이터 조립
    rankings = []
    for p in all_parks:
        rankings.append({
            'park': p,
            'wins': win_counts.get(p.id, 0),
            'losses': loss_counts.get(p.id, 0),
            'personality_emoji': personality_emojis.get(p.npc_personality, ''),
        })

    # 정렬
    if sort_by == 'power':
        rankings.sort(key=lambda x: x['park'].total_combat_power, reverse=True)
    elif sort_by == 'population':
        rankings.sort(key=lambda x: x['park'].total_population, reverse=True)
    elif sort_by == 'wins':
        rankings.sort(key=lambda x: x['wins'], reverse=True)
    elif sort_by == 'resources':
        rankings.sort(key=lambda x: x['park'].total_np_available, reverse=True)

    # 내 공원 순위 계산
    power_sorted = sorted(all_parks, key=lambda p: p.total_combat_power, reverse=True)
    pop_sorted = sorted(all_parks, key=lambda p: p.total_population, reverse=True)
    my_power_rank = next((i+1 for i, p in enumerate(power_sorted) if p.id == park.id), 0)
    my_pop_rank = next((i+1 for i, p in enumerate(pop_sorted) if p.id == park.id), 0)

    return render_template('ranking.html',
                           park=park,
                           rankings=rankings,
                           sort_by=sort_by,
                           sort_label=sort_label,
                           my_park_id=park.id,
                           total_parks=len(all_parks),
                           my_power_rank=my_power_rank,
                           my_pop_rank=my_pop_rank,
                           my_wins=win_counts.get(park.id, 0),
                           my_losses=loss_counts.get(park.id, 0))


@game_bp.route('/scout/<int:target_id>')
@login_required
def scout(target_id):
    """정찰 - 감시탑이 있으면 상세 정보, 없으면 기본 정보만"""
    park = current_user.park
    target = Park.query.get_or_404(target_id)

    if target.id == park.id:
        flash(get_text('flash.scout_self'), 'warning')
        return redirect(url_for('game.dashboard'))

    # 감시탑 유무에 따라 정보 수준 결정
    has_watchtower = park.watchtowers > 0
    scout_data = {
        'name': target.name,
        'is_npc': target.is_npc,
        'npc_personality': target.npc_personality if target.is_npc else None,
        'total_population': target.total_population,
        'is_destroyed': target.is_destroyed,
    }

    if has_watchtower:
        # 감시탑 보유: 상세 정보 공개
        scout_data.update({
            'guard_count': target.guard_count,
            'adult_count': target.adult_count,
            'child_count': target.child_count,
            'baby_count': target.baby_count,
            'total_combat_power': target.total_combat_power,
            'defense_power': target.defense_power,
            'walls': target.walls,
            'morale': target.morale,
            'watchtowers': target.watchtowers,
        })

    return jsonify({
        'has_watchtower': has_watchtower,
        'data': scout_data,
        'message': '🗼 감시탑에서 정찰 성공 데스!' if has_watchtower
                   else '👁️ 기본 정보만 파악 가능 데스... 감시탑을 세워달라 데스!'
    })


# ============================================================
# [v0.4.0] Phase 5: 교역 시스템
# ============================================================

@game_bp.route('/trade')
@login_required
def trade_market():
    """교역 시장 - 공개 교역 목록 및 내게 온 제안 표시"""
    from app.models import TradeOffer, Diplomacy
    park = current_user.park
    if not park or park.is_destroyed:
        return redirect(url_for('game.dashboard'))

    # 공개 교역 (receiver_id가 NULL이고 pending인 것, 자기 제안 제외)
    public_trades = TradeOffer.query.filter(
        TradeOffer.status == 'pending',
        TradeOffer.sender_id != park.id,
        TradeOffer.receiver_id == None
    ).order_by(TradeOffer.created_at.desc()).limit(20).all()

    # 내게 온 교역 제안 (receiver_id가 내 공원이고 pending)
    my_incoming = TradeOffer.query.filter_by(
        receiver_id=park.id, status='pending'
    ).order_by(TradeOffer.created_at.desc()).all()

    # 내가 보낸 교역 제안 (pending만)
    my_outgoing = TradeOffer.query.filter_by(
        sender_id=park.id, status='pending'
    ).order_by(TradeOffer.created_at.desc()).all()

    # 다른 공원 목록 (교역 대상 선택용, NPC 포함)
    other_parks = Park.query.filter(
        Park.id != park.id,
        Park.is_destroyed == False
    ).all()

    # 외교 관계 조회
    alliances = Diplomacy.query.filter(
        ((Diplomacy.park_a_id == park.id) | (Diplomacy.park_b_id == park.id)),
        Diplomacy.relation_type == 'ally',
        Diplomacy.status == 'active'
    ).all()

    enemies = Diplomacy.query.filter(
        ((Diplomacy.park_a_id == park.id) | (Diplomacy.park_b_id == park.id)),
        Diplomacy.relation_type == 'enemy',
        Diplomacy.status == 'active'
    ).all()

    # 동맹 요청 (내게 온 pending)
    alliance_requests = Diplomacy.query.filter(
        Diplomacy.park_b_id == park.id,
        Diplomacy.relation_type == 'ally',
        Diplomacy.status == 'pending'
    ).all()

    return render_template('trade.html',
                           park=park,
                           public_trades=public_trades,
                           my_incoming=my_incoming,
                           my_outgoing=my_outgoing,
                           other_parks=other_parks,
                           alliances=alliances,
                           enemies=enemies,
                           alliance_requests=alliance_requests)


@game_bp.route('/trade/create', methods=['POST'])
@login_required
def trade_create():
    """교역 제안 생성"""
    from app.models import TradeOffer
    from app.game_engine import add_event
    park = current_user.park
    if not park or park.is_destroyed:
        return redirect(url_for('game.dashboard'))

    # 폼에서 값 읽기
    receiver_id = request.form.get('receiver_id', type=int)  # 0이면 공개
    offer_konpeito = request.form.get('offer_konpeito', 0, type=int)
    offer_trash = request.form.get('offer_trash', 0, type=int)
    offer_material = request.form.get('offer_material', 0, type=int)
    offer_babies = request.form.get('offer_babies', 0, type=int)
    request_konpeito = request.form.get('request_konpeito', 0, type=int)
    request_trash = request.form.get('request_trash', 0, type=int)
    request_material = request.form.get('request_material', 0, type=int)
    request_babies = request.form.get('request_babies', 0, type=int)
    msg = request.form.get('trade_message', '')[:200]

    # 검증: 최소 하나는 제안하고, 최소 하나는 요청해야 함
    total_offer = offer_konpeito + offer_trash + offer_material + offer_babies
    total_req = request_konpeito + request_trash + request_material + request_babies
    if total_offer == 0 or total_req == 0:
        flash(get_text('flash.trade_empty'), 'error')
        return redirect(url_for('game.trade_market'))

    # 검증: 보유량 확인
    if offer_konpeito > park.konpeito or offer_trash > park.trash_food \
       or offer_material > park.material or offer_babies > park.baby_count:
        flash(get_text('flash.trade_insufficient'), 'error')
        return redirect(url_for('game.trade_market'))

    trade = TradeOffer(
        sender_id=park.id,
        receiver_id=receiver_id if receiver_id and receiver_id > 0 else None,
        offer_konpeito=max(0, offer_konpeito),
        offer_trash=max(0, offer_trash),
        offer_material=max(0, offer_material),
        offer_babies=max(0, offer_babies),
        request_konpeito=max(0, request_konpeito),
        request_trash=max(0, request_trash),
        request_material=max(0, request_material),
        request_babies=max(0, request_babies),
        message=msg,
    )
    db.session.add(trade)
    add_event(park, 'trade', f'📦 교역 제안 등록! (제공: 🍬{offer_konpeito} 🗑️{offer_trash} 🧱{offer_material} 🐛{offer_babies})')
    db.session.commit()

    flash(get_text('flash.trade_registered'), 'success')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/trade/accept/<int:trade_id>', methods=['POST'])
@login_required
def trade_accept(trade_id):
    """교역 제안 수락 - 자원 교환 실행"""
    from app.models import TradeOffer
    from app.game_engine import add_event
    from datetime import datetime
    park = current_user.park
    if not park or park.is_destroyed:
        return redirect(url_for('game.dashboard'))

    # [v1.5.0] Double Spend 방지: 원자적 UPDATE-WHERE로 동시 수락 차단
    # SQLite 파일 락이 UPDATE 문 단위로 걸리므로, WHERE 조건에 status를 넣으면
    # 경쟁 조건(Race Condition)이 DB 레벨에서 차단됨
    updated = TradeOffer.query.filter_by(
        id=trade_id, status='pending'
    ).update({'status': 'processing'})
    db.session.flush()

    if updated == 0:
        # 이미 다른 요청이 처리했거나 존재하지 않는 교역
        flash(get_text('flash.trade_not_found'), 'error')
        return redirect(url_for('game.trade_market'))

    trade = TradeOffer.query.get(trade_id)

    # 자기 자신의 제안은 수락 불가
    if trade.sender_id == park.id:
        trade.status = 'pending'  # 원복
        db.session.commit()
        flash(get_text('flash.trade_self'), 'error')
        return redirect(url_for('game.trade_market'))

    # 지정 교역이면 내가 대상인지 확인
    if trade.receiver_id and trade.receiver_id != park.id:
        trade.status = 'pending'  # 원복
        db.session.commit()
        flash(get_text('flash.trade_not_mine'), 'error')
        return redirect(url_for('game.trade_market'))

    sender = Park.query.get(trade.sender_id)
    if not sender or sender.is_destroyed:
        trade.status = 'expired'
        db.session.commit()
        flash(get_text('flash.trade_sender_dead'), 'warning')
        return redirect(url_for('game.trade_market'))

    # 보유량 재확인 (발송자)
    if (trade.offer_konpeito > sender.konpeito or
        trade.offer_trash > sender.trash_food or
        trade.offer_material > sender.material or
        trade.offer_babies > sender.baby_count):
        trade.status = 'expired'
        db.session.commit()
        flash(get_text('flash.trade_sender_poor'), 'warning')
        return redirect(url_for('game.trade_market'))

    # 수락자 보유량 확인 (내가 줄 것)
    if (trade.request_konpeito > park.konpeito or
        trade.request_trash > park.trash_food or
        trade.request_material > park.material or
        trade.request_babies > park.baby_count):
        trade.status = 'pending'  # 원복 (내 자원 부족이므로 교역은 유효)
        db.session.commit()
        flash(get_text('flash.trade_my_insufficient'), 'error')
        return redirect(url_for('game.trade_market'))

    # === 자원 교환 실행 ===
    # [v1.5.0] 자원 음수 방어: max(0, ...) 클램핑 적용
    # 발송자 → 수락자 (offer)
    sender.konpeito = max(0, sender.konpeito - trade.offer_konpeito)
    sender.trash_food = max(0, sender.trash_food - trade.offer_trash)
    sender.material = max(0, sender.material - trade.offer_material)
    sender.baby_count = max(0, sender.baby_count - trade.offer_babies)

    park.konpeito = min(park.konpeito + trade.offer_konpeito, park.konpeito_cap)
    park.trash_food = min(park.trash_food + trade.offer_trash, park.trash_food_cap)
    park.material = min(park.material + trade.offer_material, park.material_cap)
    park.baby_count += trade.offer_babies

    # 수락자 → 발송자 (request)
    park.konpeito = max(0, park.konpeito - trade.request_konpeito)
    park.trash_food = max(0, park.trash_food - trade.request_trash)
    park.material = max(0, park.material - trade.request_material)
    park.baby_count = max(0, park.baby_count - trade.request_babies)

    sender.konpeito = min(sender.konpeito + trade.request_konpeito, sender.konpeito_cap)
    sender.trash_food = min(sender.trash_food + trade.request_trash, sender.trash_food_cap)
    sender.material = min(sender.material + trade.request_material, sender.material_cap)
    sender.baby_count += trade.request_babies

    trade.status = 'accepted'
    trade.resolved_at = datetime.utcnow()

    add_event(park, 'trade', f'📦 교역 성사! {sender.name}에서 자원 교환 완료 데스!')
    add_event(sender, 'trade', f'📦 교역 성사! {park.name}이 교역을 수락해줬는 데스!')
    db.session.commit()

    flash(get_text('flash.trade_success', name=sender.name), 'success')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/trade/reject/<int:trade_id>', methods=['POST'])
@login_required
def trade_reject(trade_id):
    """교역 제안 거절"""
    from app.models import TradeOffer
    from datetime import datetime
    park = current_user.park
    trade = TradeOffer.query.get(trade_id)
    if not trade or trade.status != 'pending':
        flash(get_text('flash.trade_already'), 'error')
        return redirect(url_for('game.trade_market'))

    trade.status = 'rejected'
    trade.resolved_at = datetime.utcnow()
    db.session.commit()
    flash(get_text('flash.trade_rejected'), 'info')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/trade/cancel/<int:trade_id>', methods=['POST'])
@login_required
def trade_cancel(trade_id):
    """내 교역 제안 취소"""
    from app.models import TradeOffer
    from datetime import datetime
    park = current_user.park
    trade = TradeOffer.query.get(trade_id)
    if not trade or trade.sender_id != park.id or trade.status != 'pending':
        flash(get_text('flash.trade_cancel_fail'), 'error')
        return redirect(url_for('game.trade_market'))

    trade.status = 'cancelled'
    trade.resolved_at = datetime.utcnow()
    db.session.commit()
    flash(get_text('flash.trade_cancelled'), 'info')
    return redirect(url_for('game.trade_market'))


# ============================================================
# [v0.4.0] Phase 5: 외교 시스템
# ============================================================

@game_bp.route('/diplomacy/ally/<int:target_id>', methods=['POST'])
@login_required
def diplomacy_ally(target_id):
    """동맹 요청 보내기"""
    from app.models import Diplomacy
    from app.game_engine import add_event
    park = current_user.park
    target = Park.query.get(target_id)
    if not target or target.is_destroyed or target.id == park.id:
        flash(get_text('flash.diplo_invalid'), 'error')
        return redirect(url_for('game.trade_market'))

    # 이미 관계가 있는지 확인
    existing = Diplomacy.query.filter(
        ((Diplomacy.park_a_id == park.id) & (Diplomacy.park_b_id == target.id)) |
        ((Diplomacy.park_a_id == target.id) & (Diplomacy.park_b_id == park.id)),
        Diplomacy.status.in_(['pending', 'active'])
    ).first()
    if existing:
        flash(get_text('flash.diplo_exists'), 'warning')
        return redirect(url_for('game.trade_market'))

    # NPC에게는 자동 수락
    if target.is_npc:
        diplo = Diplomacy(park_a_id=park.id, park_b_id=target.id,
                          relation_type='ally', status='active')
        add_event(park, 'diplomacy', f'🤝 {target.name}과(와) 동맹을 맺었는 데스!')
    else:
        diplo = Diplomacy(park_a_id=park.id, park_b_id=target.id,
                          relation_type='ally', status='pending')
        add_event(target, 'diplomacy', f'🤝 {park.name}이 동맹을 제안했는 데스!')
        add_event(park, 'diplomacy', f'🤝 {target.name}에게 동맹 요청을 보냈는 데스!')

    db.session.add(diplo)
    db.session.commit()
    flash(get_text('flash.diplo_ally_sent', name=target.name) if not target.is_npc
          else get_text('flash.diplo_ally_auto', name=target.name), 'success')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/diplomacy/accept/<int:diplo_id>', methods=['POST'])
@login_required
def diplomacy_accept(diplo_id):
    """동맹 요청 수락"""
    from app.models import Diplomacy
    from app.game_engine import add_event
    from datetime import datetime
    park = current_user.park
    diplo = Diplomacy.query.get(diplo_id)
    if not diplo or diplo.park_b_id != park.id or diplo.status != 'pending':
        flash(get_text('flash.diplo_accept_fail'), 'error')
        return redirect(url_for('game.trade_market'))

    diplo.status = 'active'
    diplo.resolved_at = datetime.utcnow()
    add_event(park, 'diplomacy', f'🤝 {diplo.park_a.name}과(와) 동맹 성사!')
    add_event(diplo.park_a, 'diplomacy', f'🤝 {park.name}이 동맹을 수락해줬는 데스!')
    db.session.commit()
    flash(get_text('flash.diplo_ally_success', name=diplo.park_a.name), 'success')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/diplomacy/reject/<int:diplo_id>', methods=['POST'])
@login_required
def diplomacy_reject(diplo_id):
    """동맹 요청 거절"""
    from app.models import Diplomacy
    from datetime import datetime
    park = current_user.park
    diplo = Diplomacy.query.get(diplo_id)
    if not diplo or diplo.park_b_id != park.id or diplo.status != 'pending':
        flash(get_text('flash.diplo_accept_fail'), 'error')
        return redirect(url_for('game.trade_market'))

    diplo.status = 'rejected'
    diplo.resolved_at = datetime.utcnow()
    db.session.commit()
    flash(get_text('flash.diplo_reject'), 'info')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/diplomacy/enemy/<int:target_id>', methods=['POST'])
@login_required
def diplomacy_enemy(target_id):
    """적대 선언 (일방적, 즉시 활성)"""
    from app.models import Diplomacy
    from app.game_engine import add_event
    park = current_user.park
    target = Park.query.get(target_id)
    if not target or target.is_destroyed or target.id == park.id:
        flash(get_text('flash.diplo_invalid'), 'error')
        return redirect(url_for('game.trade_market'))

    # 기존 동맹이 있으면 해제
    existing_ally = Diplomacy.query.filter(
        ((Diplomacy.park_a_id == park.id) & (Diplomacy.park_b_id == target.id)) |
        ((Diplomacy.park_a_id == target.id) & (Diplomacy.park_b_id == park.id)),
        Diplomacy.relation_type == 'ally',
        Diplomacy.status == 'active'
    ).first()
    if existing_ally:
        existing_ally.status = 'dissolved'

    # 이미 적대 관계인지 확인
    existing_enemy = Diplomacy.query.filter(
        ((Diplomacy.park_a_id == park.id) & (Diplomacy.park_b_id == target.id)) |
        ((Diplomacy.park_a_id == target.id) & (Diplomacy.park_b_id == park.id)),
        Diplomacy.relation_type == 'enemy',
        Diplomacy.status == 'active'
    ).first()
    if existing_enemy:
        flash(get_text('flash.diplo_exists'), 'warning')
        return redirect(url_for('game.trade_market'))

    diplo = Diplomacy(park_a_id=park.id, park_b_id=target.id,
                      relation_type='enemy', status='active')
    db.session.add(diplo)
    add_event(park, 'diplomacy', f'⚔️ {target.name}에 적대를 선언했는 데스!!')
    add_event(target, 'diplomacy', f'⚔️ {park.name}이 적대를 선언했는 데스!! 경계하라 데스!')
    db.session.commit()

    flash(get_text('flash.diplo_enemy_sent', name=target.name), 'warning')
    return redirect(url_for('game.trade_market'))


@game_bp.route('/diplomacy/dissolve/<int:diplo_id>', methods=['POST'])
@login_required
def diplomacy_dissolve(diplo_id):
    """외교 관계 해제 (동맹 파기 / 적대 종료)"""
    from app.models import Diplomacy
    from app.game_engine import add_event
    from datetime import datetime
    park = current_user.park
    diplo = Diplomacy.query.get(diplo_id)
    if not diplo or diplo.status != 'active':
        flash(get_text('flash.diplo_break_fail'), 'error')
        return redirect(url_for('game.trade_market'))

    # 본인이 관련된 관계인지 확인
    if diplo.park_a_id != park.id and diplo.park_b_id != park.id:
        flash(get_text('flash.diplo_not_mine'), 'error')
        return redirect(url_for('game.trade_market'))

    other = diplo.park_b if diplo.park_a_id == park.id else diplo.park_a
    diplo.status = 'dissolved'
    diplo.resolved_at = datetime.utcnow()
    add_event(park, 'diplomacy', f'📜 {other.name}과(와)의 {diplo.relation_type} 관계를 해제했는 데스.')
    if not other.is_destroyed:
        add_event(other, 'diplomacy', f'📜 {park.name}이 {diplo.relation_type} 관계를 해제했는 데스.')
    db.session.commit()

    flash(get_text('flash.diplo_break'), 'info')
    return redirect(url_for('game.trade_market'))

