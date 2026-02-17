# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 대사 데이터베이스 (dialogues.py)
[v1.3.0] i18n 대사 시스템 - JSON 기반 다국어 대사 로더.

말투 규칙 (언어별):
- 한국어: ~데스(desu), ~테츄(techu), 레후(refu)
- 일본어: ~でち(dechi), ~テチュ(techu), レフ(refu) ← 원작
- 영어: ~desu, ~techu, ~refu (로마자)
- 중국어: ~的說/的说, ~嘚啾, 嘞呼

대사 데이터는 app/lang/dialogues_{lang}.json 파일에 저장.
키 구조: GATHER_DEPART, BUILD_START 등은 dict/list/str 타입.
"""
import json
import os
import random

# JSON 대사 캐시 (언어별)
_dialogue_cache = {}

# 기본 언어 (폴백)
_DEFAULT_LANG = 'ko'


def _load_dialogues(lang_code):
    """
    [v1.3.0] 지정 언어의 대사 JSON을 로드하여 캐시.
    없는 언어면 기본 언어(ko)로 폴백.
    """
    global _dialogue_cache
    if lang_code in _dialogue_cache:
        return _dialogue_cache[lang_code]

    lang_dir = os.path.join(os.path.dirname(__file__), 'lang')
    filepath = os.path.join(lang_dir, f'dialogues_{lang_code}.json')

    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            _dialogue_cache[lang_code] = json.load(f)
    else:
        # 해당 언어 파일 없으면 기본 언어 로드
        fallback_path = os.path.join(lang_dir, f'dialogues_{_DEFAULT_LANG}.json')
        if os.path.exists(fallback_path):
            with open(fallback_path, 'r', encoding='utf-8') as f:
                _dialogue_cache[lang_code] = json.load(f)
        else:
            _dialogue_cache[lang_code] = {}

    return _dialogue_cache[lang_code]


def _get_current_lang():
    """Flask 세션에서 현재 언어 취득 (요청 컨텍스트 외에서는 기본값)"""
    try:
        from flask import session
        return session.get('lang', _DEFAULT_LANG)
    except RuntimeError:
        # Flask 요청 컨텍스트 밖 (스케줄러 등)
        return _DEFAULT_LANG


def _get_data(key, lang=None):
    """
    [v1.3.0] 키에 해당하는 대사 데이터를 가져온다.
    반환: list, dict, str 중 하나 (원본 그대로).
    없으면 기본 언어에서 조회, 그래도 없으면 빈 리스트.
    """
    if lang is None:
        lang = _get_current_lang()

    data = _load_dialogues(lang)
    result = data.get(key)

    # 해당 언어에 없으면 기본 언어에서 폴백
    if result is None and lang != _DEFAULT_LANG:
        fallback = _load_dialogues(_DEFAULT_LANG)
        result = fallback.get(key)

    return result if result is not None else []


# ========================================
# 대사 상수 프로퍼티 (기존 코드 호환용)
# ========================================
# 기존 `DLG.GATHER_SUCCESS_BIG` 같은 접근 방식과 호환되도록
# 모듈 레벨 속성으로 동적 로딩 지원

class _DialogueProxy:
    """
    [v1.3.0] 모듈 속성 접근을 JSON 로더로 프록시.
    기존 코드에서 DLG.GATHER_SUCCESS_BIG 같은 접근을 유지하면서
    현재 세션 언어에 맞는 대사를 반환한다.
    """
    def __getattr__(self, name):
        # 내부 속성이나 함수는 무시
        if name.startswith('_'):
            raise AttributeError(name)
        return _get_data(name)


# 프록시 인스턴스 (import 시 사용)
_proxy = _DialogueProxy()


def __getattr__(name):
    """
    [v1.3.0] 모듈 레벨 __getattr__ (Python 3.7+)
    DLG.GATHER_SUCCESS_BIG 같은 접근을 프록시로 위임.
    """
    # random, os, json 등 실제 모듈 속성은 정상 반환
    if name in ('random', 'os', 'json', '_dialogue_cache',
                '_DEFAULT_LANG', '_proxy', '_DialogueProxy'):
        raise AttributeError(name)

    return _get_data(name)


# ========================================
# 유틸리티 함수 (기존 호환)
# ========================================

def get_random_dialogues(dialogue_data, count=2):
    """
    대사 데이터에서 랜덤으로 count개 선택하여 반환.
    dialogue_data: list 또는 키 문자열.
    """
    # 키 문자열이 들어오면 로드
    if isinstance(dialogue_data, str) and dialogue_data.isupper():
        dialogue_data = _get_data(dialogue_data)

    if isinstance(dialogue_data, str):
        return [dialogue_data]

    if not dialogue_data:
        return []

    if len(dialogue_data) <= count:
        return dialogue_data[:]
    return random.sample(dialogue_data, count)


def get_random_dialogue(dialogue_data):
    """
    대사 데이터에서 랜덤 1개 선택.
    dialogue_data: list, str, 또는 키 문자열.
    """
    # 키 문자열이 들어오면 로드
    if isinstance(dialogue_data, str) and dialogue_data.isupper():
        dialogue_data = _get_data(dialogue_data)

    if isinstance(dialogue_data, str):
        return dialogue_data
    if not dialogue_data:
        return ""
    return random.choice(dialogue_data)


def get_dialogue_dict(key, sub_key, lang=None):
    """
    [v1.3.0] dict 타입 대사에서 서브키로 조회.
    예: get_dialogue_dict('BATTLE_DEPART', 'guard')
    반환: list
    """
    data = _get_data(key, lang)
    if isinstance(data, dict):
        result = data.get(sub_key, data.get('default', []))
        return result if isinstance(result, list) else [result]
    return data if isinstance(data, list) else [str(data)]
