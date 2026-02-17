# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 턴 스케줄러 (turn_scheduler.py)
[v0.2.0] APScheduler를 이용한 자동 턴 처리.

매 TURN_INTERVAL(기본 10분)마다 모든 공원의 턴을 자동 처리한다.
- 플레이어 공원: 식량 소비, 건설 진행, 훈련 판정, 성장, 기아
- NPC 공원: 위 + AI 행동 (채집, 건설, 침공 등)
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# 전역 스케줄러 인스턴스
scheduler = BackgroundScheduler(daemon=True)


def init_scheduler(app):
    """Flask 앱에 턴 스케줄러 연결"""
    from app.config import GameConfig as GC

    # 이미 실행 중이면 중복 방지
    if scheduler.running:
        return

    # 턴 처리 작업 등록
    scheduler.add_job(
        func=_process_all_turns,
        trigger=IntervalTrigger(seconds=GC.TURN_INTERVAL),
        id='turn_processor',
        name='실장석 공원 턴 처리 데스!',
        replace_existing=True,
        kwargs={'app': app},
    )

    scheduler.start()
    app.logger.info(f"[스케줄러] 턴 처리 시작! 간격: {GC.TURN_INTERVAL}초")


def _process_all_turns(app):
    """
    모든 활성 공원의 턴을 일괄 처리.
    Flask 앱 컨텍스트 내에서 실행해야 DB 접근 가능.
    """
    with app.app_context():
        from app.models import db, Park
        from app.game_engine import process_turn
        from app.npc_engine import process_npc_turn

        # 멸망하지 않은 모든 공원
        active_parks = Park.query.filter_by(is_destroyed=False).all()

        player_count = 0
        npc_count = 0

        for park in active_parks:
            try:
                # 공통 턴 처리 (식량 소비, 건설, 훈련, 성장 등)
                process_turn(park)

                # NPC 공원은 추가로 AI 행동 실행
                if park.is_npc:
                    process_npc_turn(park)
                    npc_count += 1
                else:
                    player_count += 1

            except Exception as e:
                app.logger.error(f"[턴 처리 오류] 공원 '{park.name}': {e}")
                db.session.rollback()
                continue

        db.session.commit()
        app.logger.info(
            f"[턴 완료] 플레이어 {player_count}개, NPC {npc_count}개 공원 처리 완료"
        )


def force_process_turn(app, park_id):
    """디버그/테스트용: 특정 공원의 턴을 강제 처리"""
    with app.app_context():
        from app.models import db, Park
        from app.game_engine import process_turn
        from app.npc_engine import process_npc_turn

        park = Park.query.get(park_id)
        if park and not park.is_destroyed:
            process_turn(park)
            if park.is_npc:
                process_npc_turn(park)
            db.session.commit()
            return True
    return False
