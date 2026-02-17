# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 전투 엔진 (battle_engine.py)
[v0.3.0] 침공/방어 전투 시뮬레이션.
  - 출정 유닛 선택 (경호/성체 각 인원 지정)
  - 보스실장 참전 옵션 (전투력 대폭↑, 패배 시 보스 HP↓)

전투 흐름:
1. 공격자/방어자 전투력 계산 (출정 유닛 기반)
2. 랜덤 요소 가미한 승패 판정
3. 피해 계산 (양측 사상자 - 출정 유닛에서만)
4. 승리 시 약탈 (자원 + 인구 포획)
5. 보스 참전 시 패배하면 보스 HP 감소
6. 전투 로그 + 대사 기록
"""
import random
import json
import math

from app.models import db, Park, BattleLog, EventLog
from app.config import GameConfig as GC
from app import dialogues as DLG
from app.game_engine import add_event


def execute_battle(attacker, defender, send_guards=None, send_adults=None, boss_joins=False):
    """
    전투 실행.
    매개변수:
      - send_guards: 출정 경호실장 수 (None이면 방어 배치 제외 전원)
      - send_adults: 출정 성체실장 수 (None이면 방어 배치 제외 전원)
      - boss_joins: 보스실장 참전 여부
    반환: (승리여부, 전투로그 딕셔너리, 대사 리스트)
    """
    messages = []

    # === 0. 출정 인원 결정 ===
    # 방어 배치 인원을 제외한 가용 인원
    avail_guards = max(0, attacker.guard_count - attacker.defending_guards)
    avail_adults = max(0, attacker.adult_count - attacker.defending_adults)

    # 출정 수 결정 (지정값이 없으면 전원, 가용 인원 초과 불가)
    if send_guards is None:
        send_guards = avail_guards
    else:
        send_guards = max(0, min(send_guards, avail_guards))

    if send_adults is None:
        send_adults = avail_adults
    else:
        send_adults = max(0, min(send_adults, avail_adults))

    # 최소 1명은 보내야 함
    if send_guards + send_adults == 0 and not boss_joins:
        return False, {'konpeito': 0, 'trash': 0, 'material': 0, 'babies': 0, 'children': 0}, \
            ["아무도 안 보내면 침공할 수 없는 데스!"]

    # === 1. 전투력 계산 ===
    atk_power = _calc_attack_power_selected(send_guards, send_adults, attacker.morale, boss_joins)
    def_power = _calc_defense_power(defender)

    # 랜덤 요소 (±20% 변동)
    atk_roll = atk_power * random.uniform(0.8, 1.2)
    def_roll = def_power * random.uniform(0.8, 1.2)

    # === 2. 승패 판정 ===
    attacker_wins = atk_roll > def_roll
    power_ratio = atk_roll / max(def_roll, 1)

    # 출발 대사
    if boss_joins:
        messages.append("👑 보스실장이 직접 출전하는 데스!! 전투력이 폭발적인 데스!!")
    if send_guards > 0:
        messages.append(DLG.get_random_dialogue(DLG.BATTLE_DEPART['guard']))
    elif send_adults > 0:
        messages.append(DLG.get_random_dialogue(DLG.BATTLE_DEPART['adult']))

    # === 3. 피해 계산 (출정 유닛에서만) ===
    atk_losses = _calc_losses_selected(send_guards, send_adults, power_ratio, is_winner=attacker_wins)
    def_losses = _calc_losses(defender, 1 / power_ratio, is_attacker=False)

    # 피해 적용
    attacker.guard_count = max(0, attacker.guard_count - atk_losses.get('guards', 0))
    attacker.adult_count = max(0, attacker.adult_count - atk_losses.get('adults', 0))
    _apply_losses(defender, def_losses)

    # === 4. 약탈 (공격자 승리 시) ===
    loot = {'konpeito': 0, 'trash': 0, 'material': 0, 'babies': 0, 'children': 0}

    if attacker_wins:
        loot = _calculate_loot(defender)
        _apply_loot(attacker, defender, loot)

        # 승리 대사
        messages.extend(DLG.get_random_dialogues(DLG.BATTLE_WIN, 2))
        if loot['children'] > 0:
            messages.append(DLG.get_random_dialogue(DLG.BATTLE_WIN_CAPTURED_CHILD))

        # 승리 시 사기 상승
        attacker.morale = min(100, attacker.morale + 8)
        defender.morale = max(0, defender.morale - 12)
    else:
        # 패배 대사
        messages.extend(DLG.get_random_dialogues(DLG.BATTLE_LOSE, 2))

        # 패배 시 사기 변동
        attacker.morale = max(0, attacker.morale - 8)
        defender.morale = min(100, defender.morale + 5)

    # === 5. 보스 피해 판정 ===
    if boss_joins and not attacker_wins:
        # 보스가 참전했는데 졌으면 확정 피해
        boss_dmg = random.randint(10, 25)
        attacker.boss_hp = max(0, attacker.boss_hp - boss_dmg)
        messages.append(f"👑 보스실장이 전투에서 {boss_dmg} 피해를 입은 데스!!")
        if attacker.boss_hp <= 0:
            attacker.is_destroyed = True
            messages.append("💀 보스실장이 죽었는 데스... 공원은 멸망한 데스...")
    elif not attacker_wins and power_ratio < 0.3:
        # 보스 미참전이라도 대패 시 소량 피해
        boss_dmg = random.randint(3, 10)
        attacker.boss_hp = max(0, attacker.boss_hp - boss_dmg)
        messages.append(f"👑 대패! 보스실장이 간접 피해 {boss_dmg}를 입은 데스!")
        if attacker.boss_hp <= 0:
            attacker.is_destroyed = True
            messages.append("💀 보스실장이 죽었는 데스... 공원은 멸망한 데스...")

    # 방어자 보스 피해 (대승 시)
    if attacker_wins and power_ratio > 2.0:
        boss_dmg = random.randint(5, 15)
        defender.boss_hp = max(0, defender.boss_hp - boss_dmg)
        if defender.boss_hp <= 0:
            defender.is_destroyed = True

    # === 6. 전투 로그 저장 ===
    result_text = 'win' if attacker_wins else 'lose'
    log_text = _format_battle_log(attacker, defender, attacker_wins,
                                   atk_losses, def_losses, loot,
                                   send_guards, send_adults, boss_joins)

    battle_log = BattleLog(
        attacker_id=attacker.id,
        defender_id=defender.id,
        result=result_text,
        log_text=log_text,
        loot_konpeito=loot['konpeito'],
        loot_trash=loot['trash'],
        loot_material=loot['material'],
        loot_babies=loot['babies'],
        loot_children=loot['children'],
        attacker_losses=json.dumps(atk_losses),
        defender_losses=json.dumps(def_losses),
    )
    db.session.add(battle_log)

    # 이벤트 로그 (양측)
    boss_tag = " (👑보스 출전)" if boss_joins else ""
    if attacker_wins:
        add_event(attacker, 'battle',
                  f"⚔️ {defender.name} 침공 승리!{boss_tag} "
                  f"🍬{loot['konpeito']} 🗑️{loot['trash']} "
                  f"🧱{loot['material']} 🐛{loot['babies']} 👶{loot['children']} 약탈!")
        add_event(defender, 'battle',
                  f"⚔️ {attacker.name}의 침공을 당했는 데스! 자원을 빼앗겼는 데스!!")
    else:
        add_event(attacker, 'battle',
                  f"⚔️ {defender.name} 침공 실패...{boss_tag} 피해를 입은 데스...")
        add_event(defender, 'battle',
                  f"⚔️ {attacker.name}의 침공을 막아냈는 데스!! "
                  + DLG.get_random_dialogue(DLG.BATTLE_DEFEND_WIN))

    db.session.commit()
    return attacker_wins, loot, messages


def _calc_attack_power_selected(send_guards, send_adults, morale, boss_joins):
    """출정 유닛 기반 공격력 계산"""
    base = (send_guards * GC.POWER_GUARD +
            send_adults * GC.POWER_ADULT)

    # 보스 참전 보너스
    if boss_joins:
        base += GC.POWER_BOSS

    # 사기 보정
    morale_mult = 1.0 + (morale - 50) * GC.MORALE_COMBAT_EFFECT / 50
    return max(1, int(base * morale_mult))


def _calc_defense_power(park):
    """방어자 전투력 (전체 병력 + 방벽 보너스)"""
    base = (park.guard_count * GC.POWER_GUARD +
            park.adult_count * GC.POWER_ADULT +
            park.child_count * GC.POWER_CHILD)

    # 방벽 보너스 (개당 20%)
    wall_bonus = 1.0 + park.walls * 0.2
    # 감시탑 보너스 (기습 방지 = 10%)
    tower_bonus = 1.0 + (0.1 if park.watchtowers > 0 else 0)

    morale_mult = 1.0 + (park.morale - 50) * GC.MORALE_COMBAT_EFFECT / 50
    return max(1, int(base * wall_bonus * tower_bonus * morale_mult))


def _calc_losses_selected(send_guards, send_adults, power_ratio, is_winner):
    """출정 유닛에서의 피해 계산"""
    losses = {'guards': 0, 'adults': 0, 'children': 0}

    if is_winner:
        loss_rate = random.uniform(0.05, 0.2)   # 승자: 5~20% 손실
    else:
        loss_rate = random.uniform(0.2, 0.5)     # 패자: 20~50% 손실

    losses['guards'] = min(send_guards, max(0, int(send_guards * loss_rate)))
    losses['adults'] = min(send_adults, max(0, int(send_adults * loss_rate)))

    return losses


def _calc_losses(park, power_ratio, is_attacker):
    """
    전투 피해 계산 (방어자용). power_ratio가 높을수록 피해가 적음.
    반환: {'guards': n, 'adults': n, 'children': n}
    """
    losses = {'guards': 0, 'adults': 0, 'children': 0}

    # 패배 시 피해가 더 큼
    if power_ratio < 1:
        loss_rate = random.uniform(0.2, 0.5)  # 패자: 20~50% 손실
    else:
        loss_rate = random.uniform(0.05, 0.2)  # 승자: 5~20% 손실

    losses['guards'] = min(park.guard_count, int(park.guard_count * loss_rate))
    losses['adults'] = min(park.adult_count, int(park.adult_count * loss_rate))
    losses['children'] = min(park.child_count, int(park.child_count * loss_rate * 0.5))

    return losses


def _apply_losses(park, losses):
    """전투 피해를 공원에 적용"""
    park.guard_count = max(0, park.guard_count - losses.get('guards', 0))
    park.adult_count = max(0, park.adult_count - losses.get('adults', 0))
    park.child_count = max(0, park.child_count - losses.get('children', 0))


def _calculate_loot(defender):
    """약탈량 계산 (spec.md 기준 비율)"""
    loot = {
        'konpeito': int(defender.konpeito * random.uniform(*GC.LOOT_KONPEITO_RATIO)),
        'trash': int(defender.trash_food * random.uniform(*GC.LOOT_TRASH_RATIO)),
        'material': int(defender.material * random.uniform(*GC.LOOT_MATERIAL_RATIO)),
        'babies': int(defender.baby_count * random.uniform(*GC.LOOT_BABY_RATIO)),
        'children': int(defender.child_count * random.uniform(*GC.LOOT_CHILD_RATIO)),
    }
    return loot


def _apply_loot(attacker, defender, loot):
    """약탈 적용: 방어자에서 빼고 공격자에 더함"""
    # 방어자에서 차감
    defender.konpeito = max(0, defender.konpeito - loot['konpeito'])
    defender.trash_food = max(0, defender.trash_food - loot['trash'])
    defender.material = max(0, defender.material - loot['material'])
    defender.baby_count = max(0, defender.baby_count - loot['babies'])
    defender.child_count = max(0, defender.child_count - loot['children'])

    # 공격자에게 추가 (상한 적용)
    attacker.konpeito = min(attacker.konpeito + loot['konpeito'], attacker.konpeito_cap)
    attacker.trash_food = min(attacker.trash_food + loot['trash'], attacker.trash_food_cap)
    attacker.material = min(attacker.material + loot['material'], attacker.material_cap)
    attacker.baby_count += loot['babies']
    attacker.child_count += loot['children']


def _format_battle_log(attacker, defender, attacker_wins, atk_losses, def_losses, loot,
                       send_guards=0, send_adults=0, boss_joins=False):
    """전투 결과를 텍스트 로그로 포맷"""
    lines = []
    lines.append(f"⚔️ {attacker.name} vs {defender.name}")
    lines.append(f"결과: {'🏆 공격자 승리!' if attacker_wins else '🛡️ 방어자 승리!'}")
    lines.append("")

    # 출정 편성 표시
    boss_text = " + 👑보스" if boss_joins else ""
    lines.append(f"[출정 편성] ⚔️경호 {send_guards} + 🧑성체 {send_adults}{boss_text}")
    lines.append("")

    lines.append(f"[공격자 피해]")
    lines.append(f"  ⚔️경호 -{atk_losses['guards']}, 🧑성체 -{atk_losses['adults']}")
    lines.append(f"[방어자 피해]")
    lines.append(f"  ⚔️경호 -{def_losses['guards']}, 🧑성체 -{def_losses['adults']}, "
                 f"👶자실장 -{def_losses.get('children', 0)}")

    if attacker_wins:
        lines.append("")
        lines.append(f"[약탈 내역]")
        lines.append(f"  🍬콘페이토: {loot['konpeito']}")
        lines.append(f"  🗑️음쓰: {loot['trash']}")
        lines.append(f"  🧱자재: {loot['material']}")
        lines.append(f"  🐛저실장: {loot['babies']}마리 포획")
        lines.append(f"  👶자실장: {loot['children']}마리 포획")

    return "\n".join(lines)
