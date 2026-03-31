import json
import os
from pathlib import Path
from core.database import get_db_session, Maker, Genre

def load_json(path: str) -> dict:
    if not os.path.exists(path):
        print(f"[Warn] File not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def initialize_metadata():
    session = get_db_session()
    
    # 1. Maker 로딩
    print("[1/2] Maker 데이터 로딩 중...")
    makers_data = load_json("njavtv_makers.json")
    if makers_data and "makers" in makers_data:
        count = 0
        for m in makers_data["makers"]:
            ja = m.get("japanese", "").strip()
            if not ja: continue
            
            # 중복 체크 및 업데이트
            obj = session.query(Maker).filter_by(japanese=ja).first()
            if not obj:
                obj = Maker(japanese=ja)
                session.add(obj)
            
            obj.korean = m.get("korean")
            obj.english = m.get("english")
            obj.slug = m.get("slug")
            count += 1
        print(f" - {count}개의 제작사 정보를 처리했습니다.")
    
    # 2. Genre 로딩
    print("[2/2] Genre 데이터 로딩 중...")
    genres_data = load_json("njavtv_genres_i18n.json")
    if genres_data and "genres" in genres_data:
        count = 0
        for g in genres_data["genres"]:
            ja = g.get("japanese", "").strip()
            if not ja: continue
            
            # 중복 체크 및 업데이트
            obj = session.query(Genre).filter_by(japanese=ja).first()
            if not obj:
                obj = Genre(japanese=ja)
                session.add(obj)
            
            obj.korean = g.get("korean")
            obj.english = g.get("english")
            count += 1
        print(f" - {count}개의 장르 정보를 처리했습니다.")
        
    try:
        session.commit()
        print("\n[Done] 메타데이터 초기화가 완료되었습니다.")
    except Exception as e:
        session.rollback()
        print(f"\n[Error] DB 저장 실패: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    initialize_metadata()
