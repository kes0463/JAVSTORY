import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from core.database import get_db_session, JAVMetadata
from core.translator import MetadataTranslator
from core.app_config import METADATA_CONFIG

async def migrate_translations():
    """
    기존 DB의 일본어 제목/시놉시스를 한국어로 일괄 번역.
    - 대상: original_title이 있고, title이 original_title과 거의 유사하거나 일본어를 포함하는 경우.
    """
    print("\n" + "=" * 60)
    print("  🚀 기존 메타데이터 일괄 번역 마이그레이션 시작")
    print("=" * 60)

    session = get_db_session()
    translator = MetadataTranslator()
    
    if not translator.router:
        print("❌ API 키가 설정되지 않았습니다. 설정을 확인해 주세요.")
        return

    # 번역 대상 쿼리 (단순하게 title이 비어있거나 original_title과 같거나 일본어가 섞인 경우 등)
    # 여기서는 안전하게 'title이 original_title과 동일한' 것들을 우선 대상으로 함
    rows = session.query(JAVMetadata).filter(
        (JAVMetadata.original_title.isnot(None)) & 
        ((JAVMetadata.title == JAVMetadata.original_title) | (JAVMetadata.title.is_(None)))
    ).all()

    if not rows:
        print("✅ 번역이 필요한 데이터가 없습니다.")
        return

    print(f"📊 총 {len(rows)}건의 데이터를 번역 탐색합니다...")

    success_count = 0
    fail_count = 0

    for i, row in enumerate(rows):
        print(f"\n[{i+1}/{len(rows)}] {row.product_code} 처리 중...")
        
        orig_title = row.original_title
        orig_synopsis = row.synopsis # synopsis는 original_synopsis 컬럼이 따로 없으므로 현재 값을 원문으로 간주
        
        try:
            # 1. 제목 번역
            ko_title = await translator.translate_title(row.product_code, orig_title)
            if ko_title and ko_title != orig_title:
                print(f"  - 제목: {orig_title[:30]}... -> {ko_title}")
                row.title = ko_title
            
            # 2. 시놉시스 번역 (일본어 문자가 포함된 경우에만 시도)
            # 간단한 일본어 판별 (히라가나/가타카나 포함 여부)
            has_japanese = any('\u3040' <= c <= '\u30ff' for c in (orig_synopsis or ""))
            if has_japanese:
                ko_synopsis = await translator.translate_synopsis(orig_synopsis)
                if ko_synopsis and ko_synopsis != orig_synopsis:
                    print(f"  - 시놉시스 번역 완료 (길이: {len(ko_synopsis)})")
                    row.synopsis = ko_synopsis
            
            success_count += 1
            # 중간 저장 (안전성)
            if success_count % 5 == 0:
                session.commit()
                
        except Exception as e:
            print(f"  ❌ 실패: {e}")
            fail_count += 1
            continue

    session.commit()
    session.close()

    print("\n" + "=" * 60)
    print(f"✅ 마이그레이션 완료!")
    print(f"   - 성공: {success_count}건")
    print(f"   - 실패: {fail_count}건")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(migrate_translations())
