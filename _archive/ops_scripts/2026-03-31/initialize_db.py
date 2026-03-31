from core.database import get_db_session
from sqlalchemy import text

def initialize():
    print("데이터베이스 초기화 중...")
    # get_db_session() 내부에서 Base.metadata.create_all(engine)이 호출됨
    session = get_db_session()
    
    # 테이블이 정상적으로 생성되었는지 확인
    try:
        result = session.execute(text("PRAGMA table_info(jav_metadata)"))
        columns = [row[1] for row in result]
        print(f"생성된 컬럼 목록: {columns}")
        
        if 'maker' in columns:
            print("성공: 'maker' 컬럼이 포함된 최신 스키마가 적용되었습니다.")
        else:
            print("오류: 'maker' 컬럼이 생성되지 않았습니다. 모델 정의를 확인하십시오.")
            
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    initialize()
