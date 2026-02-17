# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 게임 엔진 (game_engine.py)
[v0.1.0] 핵심 게임 로직: 채집, 솎아내기, 출산, 건설, 턴 처리.

모든 행동은 이 엔진을 통해 처리되며,
결과와 함께 랜덤 대사를 반환한다.
"""
import random
import math
from datetime import datetime, timedelta

from app.models import db, Park, BuildQueue, TrainQueue, EventLog, SpyMission
from app.config import GameConfig as GC
from app import dialogues as DLG


# ========================================
# [v1.2.0] 턴 쿼터 시스템
# ========================================

def recharge_turns(park):
    """
    [v1.2.0] 접속 시 턴 충전 계산 (온디맨드 방식).
    마지막 충전 시각부터 경과한 시간에 따라 턴을 자동 충전한다.
    반환: 충전된 턴 수
    """
    if park.is_destroyed:
        return 0

    now = datetime.utcnow()
    # 마지막 충전 시각이 없으면 현재로 설정
    if park.last_turn_regen_at is None:
        park.last_turn_regen_at = now
        db.session.commit()
        return 0

    elapsed = (now - park.last_turn_regen_at).total_seconds()
    new_turns = int(elapsed // GC.TURN_REGEN_SECONDS)

    if new_turns <= 0:
        return 0

    # 충전 (최대값 제한)
    old_quota = park.turn_quota
    park.turn_quota = min(GC.TURN_QUOTA_MAX, park.turn_quota + new_turns)
    charged = park.turn_quota - old_quota

    # 충전된 만큼의 시간만 소비 (나머지는 보존)
    park.last_turn_regen_at += timedelta(seconds=new_turns * GC.TURN_REGEN_SECONDS)

    db.session.commit()
    return charged


def get_turn_info(park):
    """
    [v1.2.0] 프론트엔드 표시용 턴 정보 반환.
    반환: dict {quota, max, next_regen_seconds, is_full}
    """
    now = datetime.utcnow()
    if park.last_turn_regen_at is None:
        park.last_turn_regen_at = now

    elapsed = (now - park.last_turn_regen_at).total_seconds()
    next_secs = max(0, int(GC.TURN_REGEN_SECONDS - elapsed))

    return {
        'quota': park.turn_quota,
        'max': GC.TURN_QUOTA_MAX,
        'next_regen_seconds': next_secs if park.turn_quota < GC.TURN_QUOTA_MAX else 0,
        'is_full': park.turn_quota >= GC.TURN_QUOTA_MAX,
    }


def consume_turn(park):
    """
    [v1.2.0] 턴 1개 소비 + process_turn 실행.
    행동 전에 호출하여 턴 진행 + AP 초기화.
    반환: (성공여부, 이벤트 메시지 리스트)
    """
    if park.is_destroyed:
        return False, ['공원이 멸망한 데스...']

    if park.turn_quota <= 0:
        return False, ['⚡ 턴이 없는 데스! 충전될 때까지 기다리라 데스!']

    # 턴 소비
    park.turn_quota -= 1

    # 턴 처리 (기존 13단계 잔혹 이벤트 포함)
    process_turn(park)

    # NPC 동기 처리 (플레이어가 턴 소비할 때만 NPC도 진행)
    if GC.TURN_NPC_SYNC:
        _sync_npc_turns()

    db.session.commit()
    return True, []


def _sync_npc_turns():
    """[v1.2.0] NPC 공원 동기 턴 처리 (플레이어 턴 소비 시 호출)"""
    from app.npc_engine import process_npc_turn
    npc_parks = Park.query.filter_by(is_npc=True, is_destroyed=False).all()
    for npc_park in npc_parks:
        process_turn(npc_park)
        process_npc_turn(npc_park)


# ========================================
# [v1.3.0] 보호 모드 시스템
# ========================================

def is_protected(park):
    """
    [v1.3.0] 보호 모드 여부 판정.
    경호실장 < PROTECT_GUARD_MIN 또는 성체실장 < PROTECT_ADULT_MIN이면 보호 상태.
    반환: bool (True = 보호 중)
    """
    if park.is_destroyed:
        return False
    return (park.guard_count < GC.PROTECT_GUARD_MIN or
            park.adult_count < GC.PROTECT_ADULT_MIN)


def check_and_enter_protection(park):
    """
    [v1.3.0] 보호 모드 진입 체크 + 자원 리셋.
    현재 자원이 보호 리셋 기준보다 낮으면 보호 리셋 수준까지 보충한다.
    (실장석은 재배치, 자원은 최소 보장)
    반환: bool (True = 보호 모드에 진입해서 자원이 보충됨)
    """
    if not is_protected(park) or park.is_destroyed:
        return False

    reset_applied = False

    # 인구 보충 (현재보다 리셋값이 높을 때만 적용)
    if park.adult_count < GC.PROTECT_RESET_ADULTS:
        park.adult_count = GC.PROTECT_RESET_ADULTS
        reset_applied = True
    if park.child_count < GC.PROTECT_RESET_CHILDREN:
        park.child_count = GC.PROTECT_RESET_CHILDREN
        reset_applied = True
    if park.baby_count < GC.PROTECT_RESET_BABIES:
        park.baby_count = GC.PROTECT_RESET_BABIES
        reset_applied = True

    # 자원 보충 (현재보다 리셋값이 높을 때만 적용)
    if park.trash_food < GC.PROTECT_RESET_TRASH:
        park.trash_food = GC.PROTECT_RESET_TRASH
        reset_applied = True
    if park.konpeito < GC.PROTECT_RESET_KONPEITO:
        park.konpeito = GC.PROTECT_RESET_KONPEITO
        reset_applied = True
    if park.material < GC.PROTECT_RESET_MATERIAL:
        park.material = GC.PROTECT_RESET_MATERIAL
        reset_applied = True

    # 사기 최소 보장
    if park.morale < 30:
        park.morale = 30
        reset_applied = True

    # 보스 HP 최소 보장
    if park.boss_hp < 50:
        park.boss_hp = 50
        reset_applied = True

    if reset_applied:
        add_event(park, 'protect',
                  f'🛡️ 보호 모드 발동! 자원과 실장석이 재배치되었는 데스! '
                  f'(경호 {GC.PROTECT_GUARD_MIN}↑ \u0026 성체 {GC.PROTECT_ADULT_MIN}↑ 시 해제)')
        db.session.commit()

    return reset_applied


def get_protection_info(park):
    """
    [v1.3.0] 보호 모드 UI 표시용 정보.
    반환: dict {is_protected, guard_progress, adult_progress,
                guard_need, adult_need}
    """
    protected = is_protected(park)
    return {
        'is_protected': protected,
        'guard_current': park.guard_count,
        'guard_min': GC.PROTECT_GUARD_MIN,
        'guard_need': max(0, GC.PROTECT_GUARD_MIN - park.guard_count),
        'adult_current': park.adult_count,
        'adult_min': GC.PROTECT_ADULT_MIN,
        'adult_need': max(0, GC.PROTECT_ADULT_MIN - park.adult_count),
    }



def add_event(park, event_type, message, turn=None):
    """이벤트 로그를 공원에 추가"""
    log = EventLog(
        park_id=park.id,
        event_type=event_type,
        message=message,
        turn_number=turn or park.turn_count,
    )
    db.session.add(log)


# ========================================
# 채집 행동 (1 AP)
# ========================================
def action_gather(park, num_adults=0, num_children=0):
    """
    채집 실행. 성체/자실장을 채집에 보내 쓰레기·콘페이토·자재를 획득.
    반환: (성공여부, 결과 딕셔너리, 대사 리스트)
    """
    messages = []

    # AP 확인
    if park.action_points < 1:
        return False, {}, ["행동 포인트가 부족한 데스! 다음 턴까지 기다리라 데스!"]

    # [v1.1.0] 태업 중이면 채집 불가
    if park.strike_turns > 0:
        return False, {}, ["✊ 성체들이 태업 중인 데스!! 채집을 거부하는 데스!!"]

    # 인원 검증 (보유 수 초과 불가)
    num_adults = min(num_adults, park.adult_count)
    num_children = min(num_children, park.child_count)

    if num_adults + num_children == 0:
        return False, {}, ["아무도 안 보내면 안 되는 데스!"]

    # AP 소비
    park.action_points -= 1

    # 채집 인원 기억 (다음 턴 기본값으로 사용)
    park.gathering_adults = num_adults
    park.gathering_children = num_children

    # 출발 대사
    if num_adults > 0:
        messages.append(DLG.get_random_dialogue(DLG.GATHER_DEPART['adult']))
    if num_children > 0:
        messages.append(DLG.get_random_dialogue(DLG.GATHER_DEPART['child']))

    # === 수확 계산 ===
    result = {'trash': 0, 'konpeito': 0, 'material': 0, 'events': []}

    # 성체실장 채집
    for _ in range(num_adults):
        result['trash'] += random.randint(*GC.GATHER_TRASH_ADULT)
        result['material'] += random.randint(*GC.GATHER_MAT_ADULT)
        # 콘페이토 발견 확률
        if random.random() < GC.GATHER_KONPEITO_ADULT_CHANCE:
            result['konpeito'] += 1

    # 자실장 채집
    for _ in range(num_children):
        result['trash'] += random.randint(*GC.GATHER_TRASH_CHILD)
        result['material'] += random.randint(*GC.GATHER_MAT_CHILD)
        if random.random() < GC.GATHER_KONPEITO_CHILD_CHANCE:
            result['konpeito'] += 1

    # [v1.1.0] 쓰레기장 철거 패널티 (수확 50% 감소)
    if park.gather_penalty_turns > 0:
        result['trash'] = int(result['trash'] * 0.5)
        result['material'] = int(result['material'] * 0.5)
        messages.append('🚛 쓰레기장 철거로 수확량이 반토막인 데스...')

    # [v1.1.0] 콘페이토 중독 패널티 (채집 효율 50% 감소)
    if park.is_addicted:
        result['trash'] = int(result['trash'] * GC.ADDICTION_GATHER_PENALTY)
        result['material'] = int(result['material'] * GC.ADDICTION_GATHER_PENALTY)
        messages.append('🍬😵 중독된 실장석들이 의욕 없이 채집하는 데스...')

    # === 랜덤 이벤트 ===
    total_gatherers = num_adults + num_children

    # 이벤트 1: 쓰레기통 대박 (쓰레기 ×3)
    if random.random() < GC.GATHER_EVT_JACKPOT_CHANCE:
        result['trash'] *= 3
        result['events'].append('jackpot')
        messages.extend(DLG.get_random_dialogues(DLG.GATHER_EVT_JACKPOT, 2))

    # 이벤트 2: 야생 실장석 발견
    if random.random() < GC.GATHER_EVT_WILDLING_CHANCE:
        # 야생 자실장 또는 저실장 포획
        if random.random() < 0.5:
            park.child_count += 1
            result['events'].append('wildling_child')
        else:
            park.baby_count += 1
            result['events'].append('wildling_baby')
        messages.extend(DLG.get_random_dialogues(DLG.GATHER_EVT_WILDLING, 2))

    # 이벤트 3: 까마귀 습격 (자실장 사망 위험)
    if num_children > 0 and random.random() < GC.GATHER_EVT_PREDATOR_CHANCE:
        park.child_count = max(0, park.child_count - 1)
        result['events'].append('predator')
        messages.extend(DLG.get_random_dialogues(DLG.GATHER_EVT_PREDATOR, 2))

    # === 자원 적용 (상한 제한) ===
    park.trash_food = min(park.trash_food + result['trash'], park.trash_food_cap)
    park.konpeito = min(park.konpeito + result['konpeito'], park.konpeito_cap)
    park.material = min(park.material + result['material'], park.material_cap)

    # 성공 대사
    if result['konpeito'] > 0:
        messages.append(DLG.get_random_dialogue(DLG.GATHER_KONPEITO_FOUND))

    if result['trash'] >= total_gatherers * 8:
        messages.extend(DLG.get_random_dialogues(DLG.GATHER_SUCCESS_BIG, 1))
    else:
        messages.append(DLG.get_random_dialogue(DLG.GATHER_SUCCESS_SMALL))

    # 이벤트 로그 저장
    summary = (f"🌿 채집 완료! 🗑️음쓰 +{result['trash']} "
               f"🍬콘페이토 +{result['konpeito']} 🧱자재 +{result['material']}")
    add_event(park, 'gather', summary)

    db.session.commit()
    return True, result, messages


# ========================================
# 솎아내기 (도살) 행동 (0 AP)
# ========================================
def action_cull(park, target_type, convert_to, count=1):
    """
    솎아내기 (도살) 실행.
    target_type: 'baby' (저실장) 또는 'child' (자실장)
    convert_to: 'food' (식량) 또는 'material' (자재)
    count: 도살할 마리 수
    반환: (성공여부, 결과, 대사 리스트)
    """
    messages = []

    # 대상 확인
    if target_type == 'baby':
        if park.baby_count < count:
            return False, {}, ["저실장이 부족한 데스!"]
    elif target_type == 'child':
        if park.child_count < count:
            return False, {}, ["자실장이 부족한 데스!"]
    else:
        return False, {}, ["뭘 솎아내라는 건지 모르겠는 데스!"]

    result = {'food': 0, 'material': 0}

    for _ in range(count):
        if target_type == 'baby':
            park.baby_count -= 1
            # 희생자 대사
            messages.append(DLG.get_random_dialogue(DLG.CULL_BABY_VICTIM))

            if convert_to == 'food':
                park.meat_stock += 1  # 저실장 고기 1개 (5NP)
                result['food'] += GC.CULL_BABY_FOOD
                messages.append(DLG.get_random_dialogue(DLG.CULL_BABY_EXECUTOR))
            else:
                park.material = min(park.material + GC.CULL_BABY_MAT, park.material_cap)
                result['material'] += GC.CULL_BABY_MAT
                messages.append(DLG.get_random_dialogue(DLG.CULL_BABY_TO_MAT))

        elif target_type == 'child':
            park.child_count -= 1
            # 자실장 희생자의 비참한 대사
            messages.append(DLG.get_random_dialogue(DLG.CULL_CHILD_VICTIM))

            if convert_to == 'food':
                park.meat_stock += 2  # 자실장 고기 2개 (10NP)
                result['food'] += GC.CULL_CHILD_FOOD
                messages.append(DLG.get_random_dialogue(DLG.CULL_CHILD_EXECUTOR))
            else:
                park.material = min(park.material + GC.CULL_CHILD_MAT, park.material_cap)
                result['material'] += GC.CULL_CHILD_MAT
                messages.append(DLG.get_random_dialogue(DLG.CULL_CHILD_TO_MAT))

    # 이벤트 로그
    emoji = '🐛' if target_type == 'baby' else '👶'
    name = '저실장' if target_type == 'baby' else '자실장'
    what = f"식량 {result['food']}NP" if convert_to == 'food' else f"자재 {result['material']}"
    add_event(park, 'cull', f"🔪 {emoji}{name} {count}마리 솎아내기 → {what}")

    db.session.commit()
    return True, result, messages


# ========================================
# 출산 행동 (2 AP)
# ========================================
def action_birth(park):
    """
    출산 실행. 성체실장 1마리가 자실장/저실장을 낳는다.
    비용: 2 AP + 30 NP
    [v1.1.0] 출산 잔혹 이벤트 추가: 사산, 기형, 대량출산, 모체 사망, 포식
    반환: (성공여부, 결과, 대사 리스트)
    """
    messages = []

    if park.action_points < 2:
        return False, {}, ["행동 포인트가 부족한 데스! 출산에는 2AP 필요한 데스!"]

    if park.adult_count < 1:
        return False, {}, ["출산할 성체실장이 없는 데스!"]

    # 영양 비용 확인 (30 NP)
    if park.total_np_available < GC.BIRTH_NP_COST:
        return False, {}, ["식량이 부족해서 출산할 수 없는 데스! 30NP 필요한 데스!"]

    # NP 소비 (쓰레기부터 소비)
    _consume_np(park, GC.BIRTH_NP_COST)

    # AP 소비
    park.action_points -= 2

    # [v1.1.0] 사산 판정 (5%)
    if random.random() < GC.BIRTH_STILLBORN_CHANCE:
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_STILLBORN))
        add_event(park, 'birth_fail', '🐣💀 사산... 식량만 소비되었는 데스...')
        park.morale = max(0, park.morale - 5)
        db.session.commit()
        return True, {'children': 0, 'babies': 0, 'event': 'stillborn'}, messages

    # 출산 결과
    new_children = random.randint(*GC.BIRTH_CHILDREN)
    new_babies = random.randint(*GC.BIRTH_BABIES)

    # [v1.1.0] 대량 출산 (8%)
    if random.random() < GC.BIRTH_MASSIVE_CHANCE:
        new_children = random.randint(8, 12)
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_MASSIVE))

    # [v1.1.0] 기형 출산 (10%) - 저실장 1마리가 사용 불가
    deform_count = 0
    if random.random() < GC.BIRTH_DEFORM_CHANCE and new_babies > 0:
        deform_count = 1
        new_babies = max(0, new_babies - 1)  # 기형 1마리는 바로 사망 처리
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_DEFORM))
        park.morale = max(0, park.morale - 3)

    # 인구 상한 확인
    space = park.population_cap - park.total_population
    new_children = min(new_children, max(0, space))

    park.child_count += new_children
    park.baby_count += new_babies

    result = {'children': new_children, 'babies': new_babies}

    # 대사
    messages.extend(DLG.get_random_dialogues(DLG.BIRTH_NORMAL, 2))
    if new_babies > 0:
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_WITH_BABY))
    if new_children >= 5:
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_MANY))

    # [v1.1.0] 모체 사망 (2%)
    if random.random() < GC.BIRTH_MOTHER_DEATH_CHANCE and park.adult_count > 1:
        park.adult_count -= 1
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_MOTHER_DEATH))
        add_event(park, 'birth_death', '🐣💀 출산 중 성체 1마리 사망...')
        park.morale = max(0, park.morale - 10)
        result['mother_died'] = True

    # [v1.1.0] 기아 상태 출산 시 포식 (3%)
    if (park.total_np_available <= 0 and
            random.random() < GC.BIRTH_CANNIBALISM_CHANCE and
            new_children > 0 and park.adult_count > 1):
        eaten = min(2, new_children)
        park.child_count -= eaten
        park.meat_stock += eaten  # 고기로 전환
        new_children -= eaten
        messages.append(DLG.get_random_dialogue(DLG.BIRTH_CANNIBALISM_EVENT))
        add_event(park, 'cannibalism', f'🐣🩸 배고픈 성체가 갓난 자실장 {eaten}마리를 포식!')
        park.morale = max(0, park.morale + GC.CANNIBALISM_MORALE_PENALTY)
        result['eaten'] = eaten

    # 이벤트 로그
    event_msg = f"🐣 출산! 👶자실장 +{new_children}, 🐛저실장 +{new_babies}"
    if deform_count > 0:
        event_msg += f" (기형 {deform_count})"
    add_event(park, 'birth', event_msg)

    db.session.commit()
    return True, result, messages


# ========================================
# 건설 행동 (1 AP)
# ========================================
def action_build(park, building_type):
    """
    건설 시작. 자재를 소비하고 건설 대기열에 추가.
    반환: (성공여부, 결과, 대사 리스트)
    """
    messages = []

    if park.action_points < 1:
        return False, {}, ["행동 포인트가 부족한 데스!"]

    # [v1.1.0] 태업 중이면 건설 불가
    if park.strike_turns > 0:
        return False, {}, ["✊ 성체들이 태업 중인 데스!! 건설을 거부하는 데스!!"]

    if building_type not in GC.BUILDINGS:
        return False, {}, ["그런 건물은 모르는 데스!"]

    bldg = GC.BUILDINGS[building_type]

    # 자재 확인
    if park.material < bldg['material_cost']:
        return False, {}, [f"자재가 부족한 데스! {bldg['material_cost']}🧱 필요한 데스!"]

    # 자재 소비 & AP 소비
    park.material -= bldg['material_cost']
    park.action_points -= 1

    # 건설 대기열에 추가
    build = BuildQueue(
        park_id=park.id,
        building_type=building_type,
        turns_remaining=bldg['turns'],
    )
    db.session.add(build)

    # 대사
    build_dialogues = DLG.BUILD_START.get(building_type, DLG.BUILD_START['default'])
    messages.extend(DLG.get_random_dialogues(build_dialogues, 2))

    # 이벤트 로그
    add_event(park, 'build',
              f"🔨 {bldg['emoji']}{bldg['name']} 건설 시작! ({bldg['turns']}턴 소요)")

    db.session.commit()
    return True, {'building': building_type, 'turns': bldg['turns']}, messages


# ========================================
# 훈련 행동 (1 AP)
# ========================================
def action_train(park):
    """
    경호실장 훈련 시작. 성체실장 1마리를 훈련에 투입.
    반환: (성공여부, 결과, 대사 리스트)
    """
    messages = []

    if park.action_points < 1:
        return False, {}, ["행동 포인트가 부족한 데스!"]

    if park.adult_count < 1:
        return False, {}, ["훈련할 성체실장이 없는 데스!"]

    if park.total_np_available < GC.TRAIN_NP_COST:
        return False, {}, [f"식량이 부족한 데스! 훈련에 {GC.TRAIN_NP_COST}NP 필요한 데스!"]

    # NP 소비
    _consume_np(park, GC.TRAIN_NP_COST)
    park.action_points -= 1
    park.adult_count -= 1  # 훈련 중이므로 인원에서 제외

    # 훈련 대기열 추가
    train = TrainQueue(
        park_id=park.id,
        turns_remaining=GC.TRAIN_TURNS,
    )
    db.session.add(train)

    messages.extend(DLG.get_random_dialogues(DLG.TRAIN_START, 2))
    add_event(park, 'train', f"📖 경호실장 훈련 시작! ({GC.TRAIN_TURNS}턴 소요)")

    db.session.commit()
    return True, {'turns': GC.TRAIN_TURNS}, messages


# ========================================
# 턴 처리 (스케줄러에서 호출)
# ========================================
def process_turn(park):
    """
    1턴 처리. 매 턴 자동으로 실행되는 로직.
    [v1.1.0] 순서: AP → 식량 → 카니발리즘 → 건설 → 훈련 → 성장 → 운치굴 →
                   재해 → 질병 → NPC악행 → 반란 → 중독 → 밀사 → 수용초과
    """
    park.turn_count += 1
    park.action_points = GC.ACTION_POINTS_PER_TURN

    # 배치 인원 조정 (죽었거나 줄어든 경우 기억값을 보유 수에 맞춤)
    park.gathering_adults = min(park.gathering_adults, park.adult_count)
    park.gathering_children = min(park.gathering_children, park.child_count)
    park.defending_guards = min(park.defending_guards, park.guard_count)
    park.defending_adults = min(park.defending_adults, park.adult_count)

    # 1. 식량 소비
    _process_food_consumption(park)

    # 2. [v1.1.0] 자동 카니발리즘 (기아 시 경호 포식)
    _process_cannibalism(park)

    # 3. 건설 진행
    _process_building(park)

    # 4. 훈련 진행
    _process_training(park)

    # 5. 성장 판정 (자실장 → 성체실장)
    _process_growth(park)

    # 6. 운치굴 저실장 증가
    _process_unchi_breeding(park)

    # 7. [v1.1.0] 재해 & 환경 이벤트
    _process_disasters(park)

    # 8. [v1.1.0] 질병 시스템
    _process_disease(park)

    # 9. [v1.1.0] NPC 악행 이벤트
    _process_human_events(park)

    # 10. [v1.1.0] 반란 & 태업
    _process_rebellion(park)

    # 11. [v1.1.0] 콘페이토 중독 판정
    _process_addiction(park)

    # 12. [v1.1.0] 밀사 임무 진행
    _process_spy_missions(park)

    # 13. 수용 인원 초과 판정
    _process_overcrowding(park)

    # 채집 패널티 턴 감소
    if park.gather_penalty_turns > 0:
        park.gather_penalty_turns -= 1

    # 태업 턴 감소
    if park.strike_turns > 0:
        park.strike_turns -= 1

    db.session.commit()


def _consume_np(park, np_needed):
    """
    영양 포인트(NP)를 소비. 우선순위: 쓰레기 → 고기 → 콘페이토.
    실제로 자원 수량을 차감한다.
    """
    remaining = np_needed

    # 1순위: 음식물 쓰레기 (1NP/개)
    if remaining > 0 and park.trash_food > 0:
        use = min(park.trash_food, remaining)
        park.trash_food -= use
        remaining -= use

    # 2순위: 식용 고기 (5NP/개, 저실장/자실장 도살분)
    if remaining > 0 and park.meat_stock > 0:
        use_meat = min(park.meat_stock, math.ceil(remaining / GC.NP_MEAT))
        park.meat_stock -= use_meat
        remaining -= use_meat * GC.NP_MEAT

    # 3순위: 콘페이토 (10NP/개)
    if remaining > 0 and park.konpeito > 0:
        use_kon = min(park.konpeito, math.ceil(remaining / GC.NP_KONPEITO))
        park.konpeito -= use_kon
        remaining -= use_kon * GC.NP_KONPEITO

    return remaining  # 0이면 정상, 양수면 부족분


def _process_food_consumption(park):
    """턴 당 식량 소비 처리"""
    np_needed = park.total_np_per_turn
    shortage = _consume_np(park, np_needed)

    # 콘페이토를 먹었는지 확인 (사기 보너스)
    ate_konpeito = park.konpeito < (park.konpeito_cap if False else park.konpeito)
    # 간단히: 쓰레기만 먹었는지 판별
    if park.konpeito <= 0 and park.meat_stock <= 0:
        park.consecutive_trash_turns += 1
    else:
        park.consecutive_trash_turns = 0

    # 사기 조정
    if park.consecutive_trash_turns >= 3:
        park.morale = max(0, park.morale + GC.MORALE_TRASH_PENALTY)
        add_event(park, 'morale',
                  DLG.get_random_dialogue(DLG.FOOD_TRASH_ONLY))

    # 기아 판정 (식량 부족 시)
    if shortage > 0:
        _process_starvation(park, shortage)


def _process_starvation(park, shortage):
    """기아 처리: 식량 부족 시 약한 개체부터 사망"""
    add_event(park, 'starve', DLG.get_random_dialogue(DLG.FOOD_STARVING))

    # 부족한 NP만큼 개체 사망 (약한 순서: 저실장 → 자실장 → 성체)
    while shortage > 0:
        if park.baby_count > 0:
            park.baby_count -= 1
            shortage -= 1
        elif park.child_count > 0:
            park.child_count -= 1
            shortage -= 2
            add_event(park, 'starve', DLG.get_random_dialogue(DLG.FOOD_DEATH))
        elif park.adult_count > 0:
            park.adult_count -= 1
            shortage -= 5
            add_event(park, 'starve', DLG.get_random_dialogue(DLG.FOOD_DEATH))
        else:
            # 모든 실장석이 죽으면 보스에게 피해
            park.boss_hp -= 10
            shortage = 0
            if park.boss_hp <= 0:
                park.is_destroyed = True
                add_event(park, 'gameover',
                          "👑 보스실장이... 굶어서... 죽었는 데스... 공원은 끝난 데스...")


def _process_building(park):
    """건설 대기열 처리"""
    for build in park.build_queue:
        build.turns_remaining -= 1
        if build.turns_remaining <= 0:
            # 건설 완료!
            btype = build.building_type
            bldg = GC.BUILDINGS.get(btype, {})

            # 시설 수 증가
            if btype == 'cardboard_house':
                park.cardboard_houses += 1
                park.population_cap += bldg['effect'].get('population_cap', 0)
            elif btype == 'unchi_hole':
                park.unchi_holes += 1
            elif btype == 'storage_hole':
                park.storage_holes += 1
                park.konpeito_cap += bldg['effect'].get('konpeito_cap', 0)
                park.trash_food_cap += bldg['effect'].get('trash_food_cap', 0)
                park.material_cap += bldg['effect'].get('material_cap', 0)
            elif btype == 'wall':
                park.walls += 1
            elif btype == 'watchtower':
                park.watchtowers += 1

            add_event(park, 'build',
                      f"🔨 {bldg.get('emoji', '🏗️')}{bldg.get('name', btype)} 완성! "
                      + DLG.get_random_dialogue(DLG.BUILD_COMPLETE))
            db.session.delete(build)


def _process_training(park):
    """훈련 대기열 처리"""
    for train in park.train_queue:
        train.turns_remaining -= 1
        if train.turns_remaining <= 0:
            # 훈련 완료 - 성공/실패 판정
            if random.random() < GC.TRAIN_SUCCESS_RATE:
                park.guard_count += 1
                add_event(park, 'train',
                          f"⚔️ 훈련 성공! " + DLG.get_random_dialogue(DLG.TRAIN_SUCCESS))
            else:
                # 실패 시 성체실장으로 복귀
                park.adult_count += 1
                add_event(park, 'train',
                          f"📖 훈련 실패... " + DLG.get_random_dialogue(DLG.TRAIN_FAIL))
            db.session.delete(train)


def _process_growth(park):
    """자실장 → 성체실장 성장 판정"""
    new_adults = 0
    remaining_children = park.child_count

    for _ in range(park.child_count):
        if random.random() < GC.CHILD_TO_ADULT_CHANCE:
            # 인구 상한 확인
            if park.total_population < park.population_cap:
                new_adults += 1
                remaining_children -= 1

    if new_adults > 0:
        park.child_count = remaining_children
        park.adult_count += new_adults
        add_event(park, 'growth',
                  f"🐣 자실장 {new_adults}마리가 성체실장으로 성장한 데스!")


def _process_unchi_breeding(park):
    """운치굴에서 저실장 자동 증가"""
    if park.unchi_holes <= 0:
        return

    new_babies = 0
    for _ in range(park.unchi_holes):
        new_babies += random.randint(1, 2)

    # 운치굴 수용 한도 확인
    baby_cap = park.baby_cap
    space = max(0, baby_cap - park.baby_count)
    actual_new = min(new_babies, space)

    if actual_new > 0:
        park.baby_count += actual_new
        add_event(park, 'breeding',
                  f"🕳️ 운치굴에서 저실장 {actual_new}마리가 자란 데스!")


def _process_overcrowding(park):
    """수용 인원 초과 판정"""
    excess = park.total_population - park.population_cap
    if excess <= 0:
        return

    # 초과 인원만큼 탈주/사망 (자실장부터)
    fled = 0
    while excess > 0 and park.child_count > 0:
        park.child_count -= 1
        excess -= 1
        fled += 1

    if fled > 0:
        add_event(park, 'overcrowd',
                  f"🏠 수용 초과! 자실장 {fled}마리가 탈주! "
                  + DLG.get_random_dialogue(DLG.OVERCROWDED))


# ============================================================
# [v1.1.0] Phase 7: 잔혹 컨텐츠 턴 처리 함수
# ============================================================

def _process_disasters(park):
    """[v1.1.0] 재해 & 환경 이벤트 (턴마다 확률 판정)"""
    if park.is_destroyed:
        return

    # 1. 폭우 - 골판지집 1동 파괴
    if random.random() < GC.DISASTER_RAIN_CHANCE and park.cardboard_houses > 0:
        park.cardboard_houses -= 1
        park.population_cap = max(5, park.population_cap - 15)
        add_event(park, 'disaster',
                  f"🌧️ 폭우! 골판지집 1동 파괴! (수용 -15) "
                  + DLG.get_random_dialogue(DLG.DISASTER_RAIN))

    # 2. 한파 - 저실장/자실장 동사
    if random.random() < GC.DISASTER_COLD_CHANCE:
        baby_dead = int(park.baby_count * 0.3)
        child_dead = int(park.child_count * 0.1)
        # 방벽이 있으면 피해 50% 감소
        if park.walls > 0:
            baby_dead = baby_dead // 2
            child_dead = child_dead // 2
        park.baby_count = max(0, park.baby_count - baby_dead)
        park.child_count = max(0, park.child_count - child_dead)
        if baby_dead + child_dead > 0:
            add_event(park, 'disaster',
                      f"❄️ 한파! 🐛저실장 -{baby_dead}, 👶자실장 -{child_dead} 동사! "
                      + DLG.get_random_dialogue(DLG.DISASTER_COLD))

    # 3. 살충제 - 운치굴 저실장 50% 사망
    if random.random() < GC.DISASTER_PESTICIDE_CHANCE and park.unchi_holes > 0:
        baby_dead = int(park.baby_count * 0.5)
        park.baby_count = max(0, park.baby_count - baby_dead)
        if baby_dead > 0:
            add_event(park, 'disaster',
                      f"☠️ 살충제! 🐛저실장 -{baby_dead} 사망! "
                      + DLG.get_random_dialogue(DLG.DISASTER_PESTICIDE))

    # 4. 쥐떼 - 식량30% + 저실장20%
    if random.random() < GC.DISASTER_RATS_CHANCE:
        food_lost = int(park.trash_food * 0.3)
        baby_dead = int(park.baby_count * 0.2)
        park.trash_food = max(0, park.trash_food - food_lost)
        park.baby_count = max(0, park.baby_count - baby_dead)
        if food_lost + baby_dead > 0:
            add_event(park, 'disaster',
                      f"🐀 쥐떼! 🗑️음쓰 -{food_lost}, 🐛저실장 -{baby_dead}! "
                      + DLG.get_random_dialogue(DLG.DISASTER_RATS))

    # 5. 고양이 - 자실장 1~3마리 사망
    if random.random() < GC.DISASTER_CAT_CHANCE and park.child_count > 0:
        killed = min(random.randint(1, 3), park.child_count)
        park.child_count -= killed
        add_event(park, 'disaster',
                  f"🐱 고양이 습격! 👶자실장 -{killed} 사망! "
                  + DLG.get_random_dialogue(DLG.DISASTER_CAT))

    # 6. 쓰레기장 철거 - 3턴 동안 채집 -50%
    if random.random() < GC.DISASTER_DUMP_REMOVAL_CHANCE and park.gather_penalty_turns <= 0:
        park.gather_penalty_turns = 3
        add_event(park, 'disaster',
                  "🚛 쓰레기장 철거! 3턴간 채집 수확 50% 감소! "
                  + DLG.get_random_dialogue(DLG.DISASTER_DUMP_REMOVAL))


def _process_cannibalism(park):
    """[v1.1.0] 자동 카니발리즘 - 기아 상태에서 경호가 자실장을 강제 포식"""
    if not GC.CANNIBALISM_AUTO_ENABLED or park.is_destroyed:
        return

    # 식량이 완전히 바닥났을 때만 발동
    if park.trash_food > 0 or park.meat_stock > 0 or park.konpeito > 0:
        return

    # 경호실장의 자실장 강제 포식 (경호 1마리당 20% 확률)
    eaten = 0
    for _ in range(park.guard_count):
        if random.random() < GC.CANNIBALISM_GUARD_FEED_CHANCE and park.child_count > 0:
            park.child_count -= 1
            park.meat_stock += 1  # 고기로 전환
            eaten += 1

    if eaten > 0:
        add_event(park, 'cannibalism',
                  f"🩸 경호실장이 자실장 {eaten}마리를 강제 포식! "
                  + DLG.get_random_dialogue(DLG.CANNIBALISM_GUARD_PREDATION))
        # 목격 사기 감소
        park.morale = max(0, park.morale + GC.CANNIBALISM_MORALE_PENALTY)
        add_event(park, 'morale', DLG.get_random_dialogue(DLG.CANNIBALISM_WITNESS))


def _process_disease(park):
    """[v1.1.0] 질병 시스템 - 과밀 시 전염병 발생/진행"""
    if park.is_destroyed:
        return

    # 이미 질병 중이면 진행
    if park.disease_turns > 0:
        park.disease_turns -= 1
        # 매 턴 피해
        baby_dead = max(1, int(park.baby_count * GC.DISEASE_BABY_DEATH_RATE))
        child_dead = max(0, int(park.child_count * GC.DISEASE_CHILD_DEATH_RATE))
        park.baby_count = max(0, park.baby_count - baby_dead)
        park.child_count = max(0, park.child_count - child_dead)
        if park.disease_turns > 0:
            add_event(park, 'disease',
                      f"🤢 전염병 진행 중! 🐛-{baby_dead} 👶-{child_dead} (남은 {park.disease_turns}턴) "
                      + DLG.get_random_dialogue(DLG.DISEASE_PROGRESS))
        else:
            add_event(park, 'disease',
                      "🤢 전염병이 자연 소멸... 많은 피해를 입은 데스...")
        return

    # 새 질병 발생 판정: 수용 90% 초과 + 운치굴 3개 이상
    if park.total_population <= 0:
        return
    occupancy = park.total_population / max(1, park.population_cap)
    if occupancy >= GC.DISEASE_OVERCROWD_THRESHOLD and park.unchi_holes >= 3:
        if random.random() < GC.DISEASE_CHANCE_PER_TURN:
            park.disease_turns = random.randint(*GC.DISEASE_DURATION)
            add_event(park, 'disease',
                      f"🤢 전염병 발생! {park.disease_turns}턴 동안 지속! "
                      + DLG.get_random_dialogue(DLG.DISEASE_OUTBREAK))


def _process_human_events(park):
    """[v1.1.0] NPC 악행 이벤트 (인간과의 상호작용)"""
    if park.is_destroyed:
        return

    # 1. 학대자 인간 (2%) - 자실장 3~5 납치
    if random.random() < GC.NPC_EVENT_ABUSER_CHANCE and park.child_count > 0:
        taken = min(random.randint(3, 5), park.child_count)
        park.child_count -= taken
        park.morale = max(0, park.morale - 8)
        add_event(park, 'human_evil',
                  f"😈 학대자 출현! 👶자실장 {taken}마리 납치! "
                  + DLG.get_random_dialogue(DLG.HUMAN_ABUSER))
        return  # 한 턴에 인간 이벤트 1회만

    # 2. 실험체 포획 (1%) - 성체 1마리
    if random.random() < GC.NPC_EVENT_EXPERIMENT_CHANCE and park.adult_count > 1:
        park.adult_count -= 1
        park.morale = max(0, park.morale - 10)
        add_event(park, 'human_evil',
                  "🔬 실험체 포획! 🧑성체 1마리 사라짐! "
                  + DLG.get_random_dialogue(DLG.HUMAN_EXPERIMENT))
        return

    # 3. 어린이 장난 (4%) - 골판지집 피해
    if random.random() < GC.NPC_EVENT_KIDS_CHANCE and park.cardboard_houses > 0:
        # 50% 확률로 골판지집 파괴, 50%는 피해만
        if random.random() < 0.5:
            park.cardboard_houses -= 1
            park.population_cap = max(5, park.population_cap - 15)
            add_event(park, 'human_evil',
                      "👦💦 어린이 장난! 골판지집 1동 파괴! "
                      + DLG.get_random_dialogue(DLG.HUMAN_KIDS))
        else:
            park.morale = max(0, park.morale - 5)
            add_event(park, 'human_evil',
                      "👦💦 어린이 장난! 물벼락으로 사기 하락! "
                      + DLG.get_random_dialogue(DLG.HUMAN_KIDS))
        return

    # 4. 착한 인간 (5%) - 선물!
    if random.random() < GC.NPC_EVENT_KINDNESS_CHANCE:
        gift_konpeito = random.randint(3, 5)
        gift_trash = random.randint(10, 20)
        park.konpeito = min(park.konpeito_cap, park.konpeito + gift_konpeito)
        park.trash_food = min(park.trash_food_cap, park.trash_food + gift_trash)
        park.morale = min(100, park.morale + 10)
        add_event(park, 'human_good',
                  f"😇 착한 인간! 🍬+{gift_konpeito} 🗑️+{gift_trash}! "
                  + DLG.get_random_dialogue(DLG.HUMAN_KINDNESS))
        return

    # 5. 펫샵 포획 (1%) - 자실장 2마리
    if random.random() < GC.NPC_EVENT_PETSHOP_CHANCE and park.child_count >= 2:
        park.child_count -= 2
        add_event(park, 'human_evil',
                  "🏪 펫샵 포획! 👶자실장 2마리 납치! "
                  + DLG.get_random_dialogue(DLG.HUMAN_PETSHOP))


def _process_rebellion(park):
    """[v1.1.0] 반란 & 태업 시스템"""
    if park.is_destroyed:
        return

    # 1. 자실장 탈주 (사기 20 이하)
    if park.morale <= GC.REBELLION_MORALE_THRESHOLD:
        if random.random() < GC.REBELLION_CHANCE:
            fled = max(1, int(park.child_count * GC.REBELLION_DESERTION_RATE))
            fled = min(fled, park.child_count)
            if fled > 0:
                park.child_count -= fled
                add_event(park, 'rebellion',
                          f"🏃 자실장 {fled}마리 탈주! "
                          + DLG.get_random_dialogue(DLG.REBELLION_DESERTION))

    # 2. 성체 태업 (사기 30 이하)
    if park.morale <= 30 and park.strike_turns <= 0:
        if random.random() < GC.REBELLION_ADULT_STRIKE_CHANCE:
            park.strike_turns = 2  # 2턴 동안 채집/건설 불가
            add_event(park, 'rebellion',
                      "✊ 성체 태업 발생! 2턴간 행동 제한! "
                      + DLG.get_random_dialogue(DLG.REBELLION_STRIKE))

    # 3. 경호 쿠데타 (사기 20 이하 + 보스 HP 30 이하)
    if (park.morale <= GC.REBELLION_MORALE_THRESHOLD and
            park.boss_hp <= GC.REBELLION_BOSS_HP_THRESHOLD and
            park.guard_count > 0):
        if random.random() < GC.REBELLION_GUARD_COUP_CHANCE:
            park.boss_hp = max(0, park.boss_hp - GC.REBELLION_GUARD_COUP_DAMAGE)
            # 쿠데타 참여 경호 50% 이탈
            coup_guards = max(1, park.guard_count // 2)
            park.guard_count -= coup_guards
            add_event(park, 'rebellion',
                      f"⚔️💀 쿠데타! 보스HP -{GC.REBELLION_GUARD_COUP_DAMAGE}, "
                      f"경호 {coup_guards}마리 이탈! "
                      + DLG.get_random_dialogue(DLG.REBELLION_GUARD_COUP))
            if park.boss_hp <= 0:
                park.is_destroyed = True
                add_event(park, 'gameover',
                          '👑💀 쿠데타로 보스실장 사망! 공원 멸망!')


def _process_addiction(park):
    """[v1.1.0] 콘페이토 중독 판정"""
    if park.is_destroyed:
        return

    # 콘페이토를 먹었는지 확인 (이번 턴에 콘페이토 소비 여부)
    ate_konpeito = park.konpeito < park.konpeito_cap  # 간이 판별
    # 더 정확한 방법: 이전 턴 대비 감소 확인이 어려우므로,
    # 콘페이토가 충분히 있고 식량 소비 중 사용되었을 가능성 판별
    has_konpeito_supply = park.konpeito > 0

    if has_konpeito_supply and park.trash_food <= 0 and park.meat_stock <= 0:
        # 콘페이토만 먹은 턴
        park.konpeito_consecutive += 1
    else:
        # 다른 식량도 먹은 턴
        if park.is_addicted:
            park.addiction_clean_turns += 1
        park.konpeito_consecutive = 0

    # 중독 발생 (3턴 연속 콘페이토만 섭취)
    if park.konpeito_consecutive >= GC.ADDICTION_TRIGGER_TURNS and not park.is_addicted:
        park.is_addicted = True
        park.addiction_clean_turns = 0
        add_event(park, 'addiction',
                  DLG.get_random_dialogue(DLG.ADDICTION_ONSET))

    # 중독 상태에서 콘페이토 없으면 사기 대폭 하락
    if park.is_addicted and park.konpeito <= 0:
        park.morale = max(0, park.morale + GC.ADDICTION_MORALE_PENALTY)
        add_event(park, 'addiction',
                  DLG.get_random_dialogue(DLG.ADDICTION_WITHDRAWAL))

    # 해독 (3턴 연속 콘페이토 미섭취)
    if park.is_addicted and park.addiction_clean_turns >= GC.ADDICTION_CURE_TURNS:
        park.is_addicted = False
        park.addiction_clean_turns = 0
        park.konpeito_consecutive = 0
        add_event(park, 'addiction',
                  DLG.get_random_dialogue(DLG.ADDICTION_CURED))


def _process_spy_missions(park):
    """[v1.1.0] 밀사 임무 진행 (해당 공원이 보낸 밀사 처리)"""
    if park.is_destroyed:
        return

    active_missions = SpyMission.query.filter_by(
        sender_id=park.id, status='active'
    ).all()

    for mission in active_missions:
        mission.turns_remaining -= 1

        if mission.turns_remaining <= 0:
            target = Park.query.get(mission.target_id)
            if not target or target.is_destroyed:
                mission.status = 'returned'
                mission.result_message = '대상 공원이 멸망한 데스...'
                continue

            # 발각 판정
            detect_chance = GC.SPY_DETECTION_CHANCE
            if target.watchtowers > 0:
                detect_chance += GC.SPY_WATCHTOWER_DETECT_BONUS

            if random.random() < detect_chance:
                # 밀사 발각 → 성체 1마리 손실 (이미 파견 시 차감했으므로 추가 손실 없음)
                mission.status = 'detected'
                mission.result_message = '밀사가 발각되어 처형당했는 데스...'
                add_event(park, 'spy',
                          f"🕵️❌ {target.name}에 보낸 밀사 발각! "
                          + DLG.get_random_dialogue(DLG.SPY_DETECTED))
                # 적 공원에도 알림
                add_event(target, 'spy',
                          DLG.get_random_dialogue(DLG.SPY_ENEMY_DETECTED))
            else:
                # 사보타주 성공
                food_ratio = random.uniform(*GC.SPY_SABOTAGE_FOOD_RATIO)
                food_destroyed = int(target.trash_food * food_ratio)
                baby_killed = min(GC.SPY_SABOTAGE_BABY_KILL, target.baby_count)
                target.trash_food = max(0, target.trash_food - food_destroyed)
                target.baby_count = max(0, target.baby_count - baby_killed)

                mission.status = 'success'
                mission.result_message = (
                    f'{target.name}: 🗑️-{food_destroyed}, 🐛-{baby_killed} 파괴!'
                )
                # 성체 1마리 복귀
                park.adult_count += 1
                add_event(park, 'spy',
                          f"🕵️✅ {target.name} 사보타주 성공! "
                          f"🗑️-{food_destroyed} 🐛-{baby_killed}! "
                          + DLG.get_random_dialogue(DLG.SPY_SUCCESS))
                add_event(target, 'sabotage',
                          f"🕵️ 밀사 사보타주 피해! 🗑️-{food_destroyed} 🐛-{baby_killed}!")


def action_cure_disease(park):
    """[v1.1.0] 질병 치료 행동 (콘페이토 5개 소비)"""
    if park.disease_turns <= 0:
        return False, {}, ['질병이 없는 데스!']

    if park.konpeito < GC.DISEASE_CURE_KONPEITO:
        return False, {}, [f'콘페이토가 부족한 데스! {GC.DISEASE_CURE_KONPEITO}개 필요한 데스!']

    park.konpeito -= GC.DISEASE_CURE_KONPEITO
    park.disease_turns = 0
    messages = DLG.get_random_dialogues(DLG.DISEASE_CURED, 1)
    add_event(park, 'disease', '💊 콘페이토 치료! 전염병 종료!')
    db.session.commit()
    return True, {'cured': True}, messages


def action_spy(park, target_id):
    """[v1.1.0] 밀사 파견 행동 (1AP + 성체 1마리)"""
    if park.action_points < GC.SPY_AP_COST:
        return False, {}, ['행동 포인트가 부족한 데스!']

    if park.adult_count < 2:  # 최소 1마리는 남겨야 함
        return False, {}, ['성체가 부족한 데스! 최소 2마리 이상 필요한 데스!']

    target = Park.query.get(target_id)
    if not target or target.is_destroyed or target.id == park.id:
        return False, {}, ['유효하지 않은 대상인 데스!']

    park.action_points -= GC.SPY_AP_COST
    park.adult_count -= 1  # 밀사로 파견

    mission = SpyMission(
        sender_id=park.id,
        target_id=target_id,
        mission_type='sabotage',
        turns_remaining=GC.SPY_RETURN_TURNS,
    )
    db.session.add(mission)

    messages = DLG.get_random_dialogues(DLG.SPY_DEPART, 1)
    add_event(park, 'spy',
              f'🕵️ {target.name}에 밀사 파견! ({GC.SPY_RETURN_TURNS}턴 후 귀환)')

    db.session.commit()
    return True, {'target': target.name, 'turns': GC.SPY_RETURN_TURNS}, messages
