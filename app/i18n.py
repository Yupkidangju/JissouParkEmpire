# -*- coding: utf-8 -*-
"""
실장석 공원 제국 - 다국어 지원 모듈 (i18n.py)
[v1.0.0] Phase 6: JSON 기반 경량 i18n 시스템.

지원 언어: 한국어(ko), 영어(en), 일본어(ja), 중국어 번체(zh_tw), 중국어 간체(zh_cn)
사용법: {{ t('key') }} 또는 Python에서 get_text('key', lang='ko')
"""
import json
import os
from flask import session, request

# 지원 언어 목록 및 표시 이름
SUPPORTED_LANGUAGES = {
    'ko': '한국어',
    'en': 'English',
    'ja': '日本語',
    'zh_tw': '繁體中文',
    'zh_cn': '简体中文',
}

# 기본 언어
DEFAULT_LANG = 'ko'

# 번역 데이터 캐시 (메모리에 로드)
_translations = {}


def _load_translations():
    """번역 JSON 파일들을 로드하여 캐시에 저장"""
    global _translations
    lang_dir = os.path.join(os.path.dirname(__file__), 'lang')
    if not os.path.exists(lang_dir):
        os.makedirs(lang_dir)

    for lang_code in SUPPORTED_LANGUAGES:
        filepath = os.path.join(lang_dir, f'{lang_code}.json')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                _translations[lang_code] = json.load(f)
        else:
            _translations[lang_code] = {}


def get_current_lang():
    """현재 세션의 언어 코드 반환"""
    return session.get('lang', DEFAULT_LANG)


def set_lang(lang_code):
    """세션에 언어 설정"""
    if lang_code in SUPPORTED_LANGUAGES:
        session['lang'] = lang_code


def get_text(key, lang=None, **kwargs):
    """
    번역 텍스트 조회.
    key: 점(.) 구분 키 (예: 'nav.dashboard', 'action.gather')
    lang: 언어 코드 (미지정 시 세션 언어)
    **kwargs: 문자열 포매팅용 변수 (예: name='test')
    """
    if not _translations:
        _load_translations()

    if lang is None:
        lang = get_current_lang()

    # 해당 언어에서 키 조회, 없으면 기본 언어, 그래도 없으면 키 자체 반환
    text = _translations.get(lang, {}).get(key)
    if text is None:
        text = _translations.get(DEFAULT_LANG, {}).get(key)
    if text is None:
        return key  # 번역 없으면 키 자체 반환 (개발 중 디버깅용)

    # 변수 치환 (예: "{name}님 환영합니다" → "testmaster님 환영합니다")
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass  # 포매팅 실패 시 원본 반환

    return text


def init_i18n(app):
    """
    Flask 앱에 i18n 초기화.
    - 템플릿에서 t() 함수 사용 가능하게 등록
    - 언어 변경 라우트 등록
    """
    # 번역 데이터 로드
    _load_translations()

    # Jinja2 전역 함수 등록: {{ t('key') }}
    @app.context_processor
    def inject_i18n():
        return {
            't': lambda key, **kw: get_text(key, **kw),
            'current_lang': get_current_lang,
            'supported_langs': SUPPORTED_LANGUAGES,
        }

    # 언어 변경 라우트
    @app.route('/set-lang/<lang_code>')
    def set_language(lang_code):
        from flask import redirect, request as req
        set_lang(lang_code)
        # 이전 페이지로 돌아가기 (Referer 활용)
        return redirect(req.referrer or '/')
