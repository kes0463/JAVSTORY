import sqlite3
from pathlib import Path
import sys

# 프로젝트 루트 삽입
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import get_db_session, Actress, Base, get_engine

def migrate():
    # 1. 새 테이블 생성 (Base.metadata.create_all 사용)
    print("메인 DB에 actresses 테이블 생성 중...")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # 2. 소스 DB 연결
    src_db = Path("actress_name.sqlite")
    if not src_db.exists():
        print(f"오류: {src_db} 파일을 찾을 수 없습니다.")
        return

    print(f"데이터 이전 시작: {src_db} -> jav_database.db")
    
    try:
        conn_src = sqlite3.connect(src_db)
        cursor_src = conn_src.cursor()
        
        # 'actress' 테이블 데이터 가져오기 (japanese, korean, romaji, source)
        cursor_src.execute("SELECT japanese, korean, romaji, source FROM actress")
        rows = cursor_src.fetchall()
        
        session = get_db_session()
        count = 0
        skipped = 0
        
        for row in rows:
            ja, ko, ro, src = row
            # 중복 체크 (DB integrity를 위해)
            exists = session.query(Actress).filter_by(japanese=ja).first()
            if not exists:
                new_actress = Actress(
                    japanese=ja,
                    korean=ko,
                    romaji=ro,
                    source=src
                )
                session.add(new_actress)
                count += 1
            else:
                skipped += 1
            
            # 대량 처리를 위해 적절히 커밋
            if count % 200 == 0:
                session.commit()
                print(f"진행 중... {count}건 이관 완료")

        session.commit()
        session.close()
        conn_src.close()
        
        print(f"마이그레이션 완료!")
        print(f" - 신규 이관: {count}건")
        print(f" - 중복 스킵: {skipped}건")
        
    except Exception as e:
        print(f"마이그레이션 중 에러 발생: {e}")

if __name__ == "__main__":
    migrate()
