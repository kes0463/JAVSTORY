import sqlite3
import sys
import os
from pathlib import Path

# 프로젝트 루트를 경로에 추가하여 core 모듈 로드 가능하게 함
sys.path.append(str(Path(__file__).parent.parent))

from core.app_config import DB_PATH

def migrate():
    print(f"[*] 데이터베이스 마이그레이션 시작: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("[!] DB 파일이 존재하지 않습니다. 마이그레이션이 필요 없습니다.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 추가할 컬럼 목록
    new_columns = [
        ("thumb_image_local_path", "TEXT"),
        ("character_relationships", "TEXT"),
        ("analysis_status", "TEXT DEFAULT 'pending'")
    ]
    
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE jav_metadata ADD COLUMN {col_name} {col_type}")
            print(f"[+] 컬럼 추가 성공: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"[-] 컬럼이 이미 존재함: {col_name}")
            else:
                print(f"[!] {col_name} 추가 중 오류: {e}")
                
    conn.commit()
    conn.close()
    print("[*] 마이그레이션 완료.")

if __name__ == "__main__":
    migrate()
