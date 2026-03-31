from core.database import get_db_session, Actress

class ActressResolver:
    """
    메인 데이터베이스(jav_database.db)의 actresses 테이블을 사용하여 
    배우의 다국어(JA, KO, Romaji) 이름을 매핑하는 클래스.
    """
    def __init__(self):
        pass

    def resolve_names(self, japanese_names: list[str]) -> dict[str, list[str]]:
        """
        일본어 이름 리스트를 받아 각 언어별 리스트로 반환.
        매핑 데이터가 없으면 원본 일본어 이름을 보관하여 추후 수동 수정을 지원함.
        """
        ja_list = []
        ko_list = []
        ro_list = []

        if not japanese_names:
            return {"ja": [], "ko": [], "romaji": []}

        session = get_db_session()
        try:
            for name in japanese_names:
                name = name.strip()
                if not name:
                    continue
                
                # 메인 DB의 actresses 테이블에서 조회
                row = session.query(Actress).filter_by(japanese=name).first()
                
                if row:
                    ja_list.append(row.japanese or name)
                    ko_list.append(row.korean or name)
                    ro_list.append(row.romaji or name)
                else:
                    # [사용자 요청 반영] 매칭 데이터가 없으면 원본 일어 이름을 한글/로마지 필드에도 보존
                    # 이는 추후 HTML 리포트에서 일본어 이름으로 표시되어 수동 수정을 용이하게 함
                    ja_list.append(name)
                    ko_list.append(name) 
                    ro_list.append(name)
        except Exception as e:
            print(f"[ActressResolver] Error: {e}")
            # 에러 발생 시 원본 리스트 반환
            return {"ja": japanese_names, "ko": japanese_names, "romaji": japanese_names}
        finally:
            session.close()

        return {
            "ja": ja_list,
            "ko": ko_list,
            "romaji": ro_list
        }

if __name__ == "__main__":
    # 테스트
    resolver = ActressResolver()
    test_names = ["三上悠亜", "白石茉莉奈"]
    result = resolver.resolve_names(test_names)
    print(f"매핑 결과: {result}")
