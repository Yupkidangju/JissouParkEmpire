# -*- coding: utf-8 -*-
"""
[v1.2.0] DB 마이그레이션 - 턴 쿼터 시스템 필드 추가
parks 테이블에 turn_quota, last_turn_regen_at 컬럼 추가
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'game.db')


def migrate():
    """v1.2.0 마이그레이션 실행"""
    if not os.path.exists(DB_PATH):
        print(f"[오류] DB 파일을 찾을 수 없습니다: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 기존 컬럼 확인
    cursor.execute("PRAGMA table_info(parks)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    # 턴 쿼터 필드 추가
    new_columns = [
        ("turn_quota", "INTEGER DEFAULT 3"),
        ("last_turn_regen_at", f"DATETIME DEFAULT '{datetime.utcnow().isoformat()}'"),
    ]

    for col_name, col_def in new_columns:
        if col_name not in existing_columns:
            sql = f"ALTER TABLE parks ADD COLUMN {col_name} {col_def}"
            cursor.execute(sql)
            print(f"  [추가] parks.{col_name} ({col_def})")
        else:
            print(f"  [존재] parks.{col_name} - 이미 있음, 스킵")

    conn.commit()
    conn.close()
    print("\n[완료] v1.2.0 마이그레이션 성공!")


if __name__ == '__main__':
    print("=" * 50)
    print("  v1.2.0 DB 마이그레이션 - 턴 쿼터 시스템")
    print("=" * 50)
    migrate()
