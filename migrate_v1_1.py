# -*- coding: utf-8 -*-
"""v1.1.0 DB 마이그레이션 - 잔혹 컨텐츠 시스템 필드 추가"""
import sqlite3

conn = sqlite3.connect('instance/game.db')
c = conn.cursor()

# 기존 컬럼 목록 확인
existing = [col[1] for col in c.execute('PRAGMA table_info(parks)').fetchall()]

# Park 테이블에 새 필드 추가
new_cols = [
    ('disease_turns', 'INTEGER DEFAULT 0'),
    ('konpeito_consecutive', 'INTEGER DEFAULT 0'),
    ('is_addicted', 'BOOLEAN DEFAULT 0'),
    ('addiction_clean_turns', 'INTEGER DEFAULT 0'),
    ('gather_penalty_turns', 'INTEGER DEFAULT 0'),
    ('strike_turns', 'INTEGER DEFAULT 0'),
]

for col_name, col_def in new_cols:
    if col_name not in existing:
        c.execute(f'ALTER TABLE parks ADD COLUMN {col_name} {col_def}')
        print(f'  Added: parks.{col_name}')
    else:
        print(f'  Exists: parks.{col_name}')

# SpyMission 테이블 생성
c.execute('''CREATE TABLE IF NOT EXISTS spy_missions (
    id INTEGER PRIMARY KEY,
    sender_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    mission_type VARCHAR(20) DEFAULT 'sabotage',
    turns_remaining INTEGER DEFAULT 3,
    status VARCHAR(20) DEFAULT 'active',
    result_message TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sender_id) REFERENCES parks(id),
    FOREIGN KEY(target_id) REFERENCES parks(id)
)''')
print('  Created/Verified: spy_missions table')

conn.commit()
conn.close()
print('DB migration v1.1.0 complete!')
