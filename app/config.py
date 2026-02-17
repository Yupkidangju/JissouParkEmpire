# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 게임 설정 (config.py)
[v0.1.0] 초기 설정. spec.md 기반 밸런스 상수 정의.

모든 게임 밸런스 수치를 이 파일에서 중앙 관리한다.
수치 변경 시 이 파일만 수정하면 게임 전체에 반영된다.
"""
import os


class Config:
    """Flask 기본 설정"""
    # Flask 시크릿 키 (세션 암호화용)
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'jissou-park-secret-desu-2026')

    # SQLite 데이터베이스 경로
    SQLALCHEMY_DATABASE_URI = 'sqlite:///game.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 디버그 모드
    DEBUG = os.environ.get('DEBUG', 'true').lower() == 'true'


class GameConfig:
    """게임 밸런스 상수 - spec.md 섹션 8 기반"""

    # === 턴 설정 ===
    TURN_INTERVAL = int(os.environ.get('TURN_INTERVAL', 600))  # 10분 (초) - NPC 처리용
    ACTION_POINTS_PER_TURN = 3  # 턴 당 행동 포인트

    # [v1.2.0] 모바일 턴 쿼터 시스템
    TURN_QUOTA_MAX = 15                # 최대 보유 턴
    TURN_QUOTA_INITIAL = 3             # 초기 턴 (가입 시)
    TURN_REGEN_SECONDS = 1200          # 1턴 충전 시간 (20분 = 1200초)
    TURN_NPC_SYNC = True               # 플레이어 턴 소비 시 NPC도 동기 처리

    # [v1.3.0] 보호 모드 시스템
    PROTECT_GUARD_MIN = 5              # 보호 해제 최소 경호실장
    PROTECT_ADULT_MIN = 15             # 보호 해제 최소 성체실장
    # 보호 모드 진입 시 재지급 자원 (초기값 + 보너스)
    PROTECT_RESET_ADULTS = 5           # 성체 5
    PROTECT_RESET_CHILDREN = 15        # 자실장 15
    PROTECT_RESET_BABIES = 8           # 저실장 8
    PROTECT_RESET_TRASH = 50           # 음쓰 50
    PROTECT_RESET_KONPEITO = 8         # 콘페이토 8
    PROTECT_RESET_MATERIAL = 80        # 자재 80

    # === 초기 자원 ===
    INITIAL_ADULTS = 3        # 성체실장 3마리
    INITIAL_CHILDREN = 10     # 자실장 10마리
    INITIAL_BABIES = 5        # 저실장 5마리
    INITIAL_GUARDS = 0        # 경호실장 0마리
    INITIAL_KONPEITO = 5      # 🍬 콘페이토 (영양가 10/개) - 희귀!
    INITIAL_TRASH_FOOD = 30   # 🗑️ 음식물 쓰레기 (영양가 1/개) - 흔함
    INITIAL_MEAT_STOCK = 0    # 🐛 식용 저실장 (영양가 5/개) - 도살로 획득
    INITIAL_MATERIAL = 50     # 🧱 자재
    INITIAL_POP_CAP = 20      # 수용 인원
    INITIAL_KONPEITO_CAP = 50
    INITIAL_TRASH_FOOD_CAP = 200
    INITIAL_MATERIAL_CAP = 100
    INITIAL_MORALE = 50       # 사기 (0~100)
    INITIAL_BOSS_HP = 100     # 보스실장 체력

    # === 식량 영양가 (NP) ===
    NP_KONPEITO = 10    # 🍬 콘페이토 = 영양 10
    NP_TRASH_FOOD = 1   # 🗑️ 음쓰 = 영양 1
    NP_MEAT = 5         # 🐛 식용 저실장 = 영양 5
    NP_CHILD_MEAT = 10  # 👶 식용 자실장 = 영양 10

    # === 식량 소비 (NP / 턴) ===
    NP_PER_GUARD = 4    # 경호실장: 많이 먹음
    NP_PER_ADULT = 3    # 성체실장
    NP_PER_CHILD = 1    # 자실장: 조금
    NP_PER_BABY = 0.5   # 저실장: 거의 안 먹음 (사육 중)

    # === 채집 효율 ===
    # 성체실장
    GATHER_TRASH_ADULT = (8, 12)           # 🗑️ 음쓰 주워오기
    GATHER_KONPEITO_ADULT_CHANCE = 0.05    # 🍬 콘페이토 발견 확률 5%
    GATHER_MAT_ADULT = (3, 5)              # 🧱 자재
    # 자실장
    GATHER_TRASH_CHILD = (2, 4)            # 🗑️ 음쓰 (서툰 데스)
    GATHER_KONPEITO_CHILD_CHANCE = 0.02    # 🍬 콘페이토 발견 확률 2%
    GATHER_MAT_CHILD = (1, 2)              # 🧱 자재
    # 이벤트
    GATHER_EVT_WILDLING_CHANCE = 0.05      # 야생 실장석 포획 기회
    GATHER_EVT_PREDATOR_CHANCE = 0.03      # 까마귀/쥐 습격
    GATHER_EVT_JACKPOT_CHANCE = 0.03       # 쓰레기통 대박 (×3 보너스)

    # === 솎아내기 (도살) ===
    CULL_BABY_FOOD = 5     # 저실장 → 식량 5NP
    CULL_BABY_MAT = 3      # 저실장 → 자재 3
    CULL_CHILD_FOOD = 10   # 자실장 → 식량 10NP
    CULL_CHILD_MAT = 5     # 자실장 → 자재 5

    # === 사기 시스템 ===
    MORALE_KONPEITO_BONUS = 10    # 콘페이토 먹으면 사기 +10
    MORALE_TRASH_PENALTY = -5     # 3턴 연속 쓰레기만 먹으면 사기 -5
    MORALE_COMBAT_EFFECT = 0.1    # 사기/100이 전투력·채집효율에 곱해짐

    # === 전투력 ===
    POWER_BOSS = 100
    POWER_GUARD = 40
    POWER_ADULT = 15
    POWER_CHILD = 2
    POWER_BABY = 0

    # === 성장 확률 ===
    CHILD_TO_ADULT_CHANCE = 0.05   # 턴당 5%
    CHILD_TO_ADULT_GUARANTEE = 10  # 10턴 후 보장

    # === 출산 ===
    BIRTH_CHILDREN = (3, 6)   # 자실장 출산 수
    BIRTH_BABIES = (1, 3)     # 저실장 출산 수
    BIRTH_NP_COST = 30        # 출산 비용 (30 NP)

    # === 건설 ===
    BUILDINGS = {
        'cardboard_house': {
            'name': '골판지집',
            'emoji': '🏠',
            'material_cost': 30,
            'turns': 3,
            'effect': {'population_cap': 15},
            'desc': '따뜻한 골판지집인 데스! 수용 인원 +15'
        },
        'unchi_hole': {
            'name': '운치굴',
            'emoji': '🕳️',
            'material_cost': 20,
            'turns': 2,
            'effect': {'baby_cap': 10},
            'desc': '냄새가 지독하지만 유용한 데스! 저실장 수용 +10'
        },
        'storage_hole': {
            'name': '저장굴',
            'emoji': '📦',
            'material_cost': 25,
            'turns': 2,
            'effect': {'konpeito_cap': 25, 'trash_food_cap': 100, 'material_cap': 50},
            'desc': '자원을 더 많이 보관할 수 있는 데스!'
        },
        'wall': {
            'name': '방벽',
            'emoji': '🧱',
            'material_cost': 40,
            'turns': 4,
            'effect': {'defense_bonus': 0.2},
            'desc': '든든한 방벽 데스! 방어력 20% 보너스!'
        },
        'watchtower': {
            'name': '감시탑',
            'emoji': '🗼',
            'material_cost': 35,
            'turns': 3,
            'effect': {'scout_bonus': True},
            'desc': '적이 오는 게 보이는 데스!'
        }
    }

    # === 훈련 ===
    TRAIN_NP_COST = 50       # 훈련 비용 (50 NP)
    TRAIN_TURNS = 3          # 훈련 기간
    TRAIN_SUCCESS_RATE = 0.6 # 성공률 60%

    # === 전투 약탈 비율 ===
    LOOT_KONPEITO_RATIO = (0.3, 0.6)   # 콘페이토 30~60% 탈취
    LOOT_TRASH_RATIO = (0.2, 0.4)      # 쓰레기 20~40% 탈취
    LOOT_MATERIAL_RATIO = (0.1, 0.3)   # 자재 10~30% 탈취
    LOOT_BABY_RATIO = (0.3, 0.5)       # 저실장 30~50% 포획
    LOOT_CHILD_RATIO = (0.1, 0.2)      # 자실장 10~20% 포획

    # === NPC 설정 ===
    NPC_INITIAL_COUNT = int(os.environ.get('NPC_INITIAL_COUNT', 8))
    NPC_TURN_GROWTH_RATE = 1.02  # 턴 당 자원 2% 성장

    # NPC 공원 이름 풀 (실장석 세계관)
    NPC_PARK_NAMES = [
        "콘페이토 동산", "야만의 골판지성", "행복의 숲",
        "피의 운치굴", "쓰레기통 왕국", "기쁨의 공원",
        "어둠의 방벽", "탐욕의 정원", "눈물의 골판지집",
        "대식가의 운치굴", "폭풍의 뒷골목", "비밀의 하수구",
        "영원의 콘페이토", "절망의 쓰레기산", "축복의 나뭇잎"
    ]

    NPC_PERSONALITIES = ['aggressive', 'defensive', 'peaceful', 'cunning', 'berserk']

    # ============================================================
    # [v1.1.0] Phase 7: 잔혹 컨텐츠 시스템 상수
    # ============================================================

    # === 1. 재해 & 환경 이벤트 (턴마다 확률 판정) ===
    DISASTER_RAIN_CHANCE = 0.05         # 폭우: 골판지집 1동 파괴 (5%)
    DISASTER_COLD_CHANCE = 0.03         # 한파: 저실장30% + 자실장10% 동사 (3%)
    DISASTER_PESTICIDE_CHANCE = 0.02    # 살충제: 운치굴 저실장 50% 사망 (2%)
    DISASTER_RATS_CHANCE = 0.04         # 쥐떼: 식량30% 소실 + 저실장20% (4%)
    DISASTER_CAT_CHANCE = 0.03          # 고양이: 자실장 1~3마리 사망 (3%)
    DISASTER_DUMP_REMOVAL_CHANCE = 0.01 # 쓰레기장 철거: 3턴 채집 -50% (1%)

    # === 2. 출산 잔혹 이벤트 (출산 시 확률 판정) ===
    BIRTH_DEFORM_CHANCE = 0.10          # 기형 출산: 저실장 1마리 운치(사용불가) (10%)
    BIRTH_STILLBORN_CHANCE = 0.05       # 사산: 출산 실패, 식량만 소비 (5%)
    BIRTH_MASSIVE_CHANCE = 0.08         # 대량 출산: 자실장 8~12마리 (8%)
    BIRTH_MOTHER_DEATH_CHANCE = 0.02    # 모체 사망: 출산 중 성체 1마리 사망 (2%)
    BIRTH_CANNIBALISM_CHANCE = 0.03     # 기아 상태 출산 시 다른 성체가 포식 (3%)

    # === 3. 자동 카니발리즘 (기아 상태에서 자동 발동) ===
    CANNIBALISM_AUTO_ENABLED = True     # 식량 0 시 자동 카니발리즘 활성
    CANNIBALISM_MORALE_PENALTY = -15    # 카니발리즘 목격 시 사기 감소
    CANNIBALISM_GUARD_FEED_CHANCE = 0.2 # 경호가 자실장 강제 포식 확률 (경호 1마리당/턴)

    # === 4. 질병 시스템 ===
    DISEASE_OVERCROWD_THRESHOLD = 0.90  # 수용 90% 초과 시 발병 판정
    DISEASE_CHANCE_PER_TURN = 0.10      # 발병 확률 10%/턴 (조건 충족 시)
    DISEASE_BABY_DEATH_RATE = 0.15      # 감염 시 저실장 매 턴 15% 사망
    DISEASE_CHILD_DEATH_RATE = 0.05     # 감염 시 자실장 매 턴 5% 사망
    DISEASE_DURATION = (3, 5)           # 지속 턴 수 (3~5턴)
    DISEASE_CURE_KONPEITO = 5           # 치료 비용: 콘페이토 5개
    DISEASE_COMBAT_PENALTY = 0.20       # 전투력 -20%

    # === 5. NPC 악행 이벤트 (턴마다 확률) ===
    NPC_EVENT_ABUSER_CHANCE = 0.02      # 학대자 인간: 자실장 3~5 납치 (2%)
    NPC_EVENT_EXPERIMENT_CHANCE = 0.01  # 실험체 포획: 성체 1마리 사라짐 (1%)
    NPC_EVENT_KIDS_CHANCE = 0.04        # 어린이 장난: 골판지집 피해 (4%)
    NPC_EVENT_KINDNESS_CHANCE = 0.05    # 착한 인간: 콘페이토+음쓰 선물 (5%)
    NPC_EVENT_PETSHOP_CHANCE = 0.01     # 펫샵 포획: 자실장 2마리 사라짐 (1%)

    # === 6. 밀사/침투 시스템 ===
    SPY_AP_COST = 1                     # 밀사 파견 비용 (1AP)
    SPY_RETURN_TURNS = 3                # 밀사 귀환까지 턴 수
    SPY_DETECTION_CHANCE = 0.40         # 밀사 발각 확률 (40%)
    SPY_WATCHTOWER_DETECT_BONUS = 0.30  # 감시탑 보유 시 적 밀사 탐지 +30%
    SPY_SABOTAGE_FOOD_RATIO = (0.10, 0.20)  # 사보타주: 식량 10~20% 파괴
    SPY_SABOTAGE_BABY_KILL = 5          # 사보타주: 저실장 5마리 도살

    # === 7. 반란 시스템 ===
    REBELLION_MORALE_THRESHOLD = 20     # 사기 20 이하 시 반란 판정
    REBELLION_BOSS_HP_THRESHOLD = 30    # 보스 HP 30 이하 시 쿠데타 가능
    REBELLION_CHANCE = 0.10             # 반란 확률 10%/턴 (조건 충족 시)
    REBELLION_GUARD_COUP_CHANCE = 0.10  # 쿠데타 확률: 경호가 보스 공격
    REBELLION_GUARD_COUP_DAMAGE = 30    # 쿠데타 성공 시 보스 HP 피해
    REBELLION_DESERTION_RATE = 0.15     # 탈주율: 자실장 15% 이탈
    REBELLION_ADULT_STRIKE_CHANCE = 0.2 # 성체 태업 확률 (사기 30 이하)

    # === 8. 콘페이토 중독 ===
    ADDICTION_TRIGGER_TURNS = 3         # 3턴 연속 콘페이토 섭취 시 중독
    ADDICTION_MORALE_PENALTY = -20      # 중독 상태에서 콘페이토 없으면 사기 -20
    ADDICTION_GATHER_PENALTY = 0.50     # 중독 실장석 채집 효율 50% 감소
    ADDICTION_CURE_TURNS = 3            # 3턴 콘페이토 미섭취 시 해독
