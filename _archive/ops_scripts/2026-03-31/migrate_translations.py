from core.database import get_db_session, JAVMetadata, Maker, Genre

def migrate_translations():
    session = get_db_session()
    records = session.query(JAVMetadata).all()
    count = 0
    
    print(f"총 {len(records)}개의 레코드를 검사 중...")
    
    for row in records:
        updated = False
        
        # 1. Maker 매핑
        if row.maker:
            m = session.query(Maker).filter_by(japanese=row.maker).first()
            if m and m.korean and row.maker != m.korean:
                row.maker = m.korean
                updated = True
        
        # 2. Genre 매핑
        if row.genres:
            input_genres = [g.strip() for g in row.genres.split(",") if g.strip()]
            translated = []
            row_updated = False
            for g_ja in input_genres:
                g_obj = session.query(Genre).filter_by(japanese=g_ja).first()
                if g_obj and g_obj.korean:
                    translated.append(g_obj.korean)
                    if g_ja != g_obj.korean:
                        row_updated = True
                else:
                    translated.append(g_ja)
            
            if row_updated:
                row.genres = ", ".join(translated)
                updated = True
        
        if updated:
            count += 1
            
    try:
        session.commit()
        print(f"[Done] {count}개의 레코드가 한국어로 성공적으로 업데이트되었습니다.")
    except Exception as e:
        session.rollback()
        print(f"[Error] 마이그레이션 실패: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate_translations()
