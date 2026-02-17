# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - NPC 엔진 (npc_engine.py)
[v0.2.0] NPC 공원의 AI 행동 결정.

5종 성격별로 턴마다 어떤 행동을 우선하는지 결정한다.
- aggressive (야만): 침공 > 채집 > 건설
- defensive (요새): 건설(방벽) > 훈련 > 채집
- peaceful (목장): 채집 > 출산 > 건설
- cunning (교활): 약한 공원만 침공, 평소엔 채집+건설
- berserk (광폭): 무조건 침공! 식량 없으면 솎아내기

각 행동은 game_engine 함수를 그대로 호출한다.
"""
import random

from app.models import db, Park
from app.config import GameConfig as GC
from app import game_engine
from app import dialogues as DLG


def process_npc_turn(park):
    """
    NPC 공원의 턴별 AI 행동.
    AP를 소비하며, 성격에 따라 행동 우선순위가 결정된다.
    """
    if park.is_destroyed or not park.is_npc:
        return

    personality = park.npc_personality or 'peaceful'

    # NPC 자원 소규모 자연 성장 (밸런스용 - 플레이어와의 격차 방지)
    _npc_passive_growth(park)

    # AP가 있는 한 행동 실행
    actions = _get_action_priority(personality, park)

    for action_func in actions:
        if park.action_points <= 0:
            break
        try:
            action_func(park)
        except Exception:
            continue  # NPC 행동 실패 시 무시


def _npc_passive_growth(park):
    """NPC 자원 소규모 자연 성장 (플레이어 대비 밸런스) [v0.3.0] 성격별 차등"""
    personality = park.npc_personality or 'peaceful'

    # 기본 쓰레기 자연 증가
    base_trash = random.randint(5, 12)
    park.trash_food = min(park.trash_food + base_trash, park.trash_food_cap)

    # 자재 소량 증가
    park.material = min(park.material + random.randint(2, 4), park.material_cap)

    # 성격별 추가 성장
    if personality == 'peaceful':
        # 목장형: 인구 번식 보너스 (저실장 +1~2)
        if random.random() < 0.3:
            park.baby_count += random.randint(1, 2)
    elif personality == 'aggressive' or personality == 'berserk':
        # 야만/광폭: 경호실장 소량 자연 증가 (10% 확률)
        if random.random() < 0.1 and park.adult_count > 2:
            park.guard_count += 1
            park.adult_count -= 1  # 성체 → 경호 자연 전환
    elif personality == 'defensive':
        # 요새형: 방벽 자비 + 자재 추가
        park.material = min(park.material + random.randint(1, 3), park.material_cap)
    elif personality == 'cunning':
        # 교활형: 콘페이토 소량 획득 (3% 확률)
        if random.random() < 0.03:
            park.konpeito = min(park.konpeito + 1, park.konpeito_cap)


def _get_action_priority(personality, park):
    """성격별 행동 우선순위 결정"""
    if personality == 'aggressive':
        return [_npc_gather, _npc_attack, _npc_train, _npc_build_wall]
    elif personality == 'defensive':
        return [_npc_build_wall, _npc_train, _npc_gather, _npc_defend]
    elif personality == 'peaceful':
        return [_npc_gather, _npc_birth, _npc_build_house, _npc_cull_if_needed]
    elif personality == 'cunning':
        return [_npc_gather, _npc_cunning_attack, _npc_build_wall, _npc_train]
    elif personality == 'berserk':
        return [_npc_attack, _npc_attack, _npc_cull_if_needed, _npc_gather]
    else:
        return [_npc_gather, _npc_build_house]


# === NPC 개별 행동 함수들 ===

def _npc_gather(park):
    """NPC 채집: 유휴 성체를 보냄"""
    if park.action_points < 1:
        return
    idle_adults = max(1, park.adult_count // 2)
    game_engine.action_gather(park, num_adults=idle_adults, num_children=0)


def _npc_birth(park):
    """NPC 출산: 인구 여유가 있고 식량 충분하면"""
    if park.action_points < 2:
        return
    if park.adult_count < 1:
        return
    if park.total_population >= park.population_cap - 3:
        return  # 인구 거의 다 참
    if park.total_np_available < GC.BIRTH_NP_COST * 2:
        return  # 식량 여유 없으면 안 함
    game_engine.action_birth(park)


def _npc_build_house(park):
    """NPC 골판지집 건설: 인구 초과 임박 시"""
    if park.action_points < 1:
        return
    if park.total_population < park.population_cap - 5:
        return  # 아직 여유 있으면 안 함
    if park.material < GC.BUILDINGS['cardboard_house']['material_cost']:
        return
    game_engine.action_build(park, 'cardboard_house')


def _npc_build_wall(park):
    """NPC 방벽 건설: 방어형/교활형"""
    if park.action_points < 1:
        return
    if park.walls >= 3:
        return  # 방벽 3개 이상이면 충분
    if park.material < GC.BUILDINGS['wall']['material_cost']:
        # 자재 부족하면 골판지집이라도
        if park.material >= GC.BUILDINGS['cardboard_house']['material_cost']:
            if park.total_population >= park.population_cap - 3:
                game_engine.action_build(park, 'cardboard_house')
        return
    game_engine.action_build(park, 'wall')


def _npc_train(park):
    """NPC 훈련: 경호실장 양성"""
    if park.action_points < 1:
        return
    if park.adult_count < 3:
        return  # 성체가 3 미만이면 훈련 안 함 (일손 부족)
    if park.guard_count >= 5:
        return  # 경호 5 이상이면 충분
    if park.total_np_available < GC.TRAIN_NP_COST:
        return
    game_engine.action_train(park)


def _npc_defend(park):
    """NPC 방어 배치: 경호실장을 방어에 배치"""
    if park.guard_count > 0:
        park.defending_guards = park.guard_count
    if park.adult_count > 2:
        park.defending_adults = park.adult_count // 3


def _npc_cull_if_needed(park):
    """NPC 솎아내기: 식량 부족 시 저실장 도살"""
    if park.total_np_available > park.total_np_per_turn * 3:
        return  # 3턴분 식량 있으면 안 함

    # 저실장 먼저 도살
    if park.baby_count > 0:
        cull_count = min(park.baby_count, 3)
        game_engine.action_cull(park, 'baby', 'food', cull_count)
    # 자실장도 위급하면
    elif park.child_count > 3 and park.total_np_available < park.total_np_per_turn:
        game_engine.action_cull(park, 'child', 'food', 1)


def _npc_attack(park):
    """NPC 공격: 다른 공원 침공 [v0.3.0] 유닛 선택 추가"""
    if park.action_points < 2:
        return
    if park.guard_count < 1 and park.adult_count < 3:
        return  # 전투 인원 부족

    # 공격 대상 찾기 (자기 제외, 머망 제외)
    targets = Park.query.filter(
        Park.id != park.id,
        Park.is_destroyed == False
    ).all()

    # [v1.3.0] 보호 모드 대상 제외
    from app.game_engine import is_protected
    targets = [t for t in targets if not is_protected(t)]

    if not targets:
        return

    # 랜덤 타겟 선택
    target = random.choice(targets)

    # [v0.3.0] NPC도 유닛 선택해서 출정 (방어 인원 제외)
    avail_guards = max(0, park.guard_count - park.defending_guards)
    avail_adults = max(0, park.adult_count - park.defending_adults)
    send_g = avail_guards  # NPC는 가용 경호 전원 출정
    send_a = avail_adults // 2  # 성체는 절반만

    from app.battle_engine import execute_battle
    execute_battle(park, target,
                   send_guards=send_g,
                   send_adults=send_a,
                   boss_joins=False)
    park.action_points -= 2


def _npc_cunning_attack(park):
    """NPC 교활 공격: 자기보다 약한 공원만 공격 [v0.3.0] 유닛 선택 추가"""
    if park.action_points < 2:
        return
    if park.guard_count < 1:
        return

    targets = Park.query.filter(
        Park.id != park.id,
        Park.is_destroyed == False
    ).all()

    # 자기보다 약한 공원만 필터링 + [v1.3.0] 보호 모드 제외
    from app.game_engine import is_protected
    weak_targets = [t for t in targets
                    if t.total_combat_power < park.total_combat_power * 0.7
                    and not is_protected(t)]

    if not weak_targets:
        return  # 약한 상대 없으면 안 싸움 (교활!)

    target = random.choice(weak_targets)

    # [v0.3.0] 교활형은 켄수를 써서 반만만 보냄 (피해 최소화)
    avail_guards = max(0, park.guard_count - park.defending_guards)
    send_g = max(1, avail_guards // 2)
    send_a = 0  # 성체는 되도록 안 보냄

    from app.battle_engine import execute_battle
    execute_battle(park, target,
                   send_guards=send_g,
                   send_adults=send_a,
                   boss_joins=False)
    park.action_points -= 2
