import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from core.translator import MetadataTranslator
from core.database import get_db_session, JAVMetadata

async def test_full_pipeline():
    print("\n" + "=" * 60)
    print("  🧪 번역 파이프라인 통합 테스트 (Title & Synopsis)")
    print("=" * 60)

    # 1. 번역기 초기화
    translator = MetadataTranslator()
    if not translator.router:
        print("❌ API 키가 설정되지 않았습니다. 설정을 확인해 주세요.")
        return

    # 2. 테스트 케이스 (실제 JAV 스타일 일본어)
    test_cases = [
        {
            "code": "STAR-471",
            "title": "義母と息子の秘密の関係 撮影場所은 집인 마이홈 旦那에 들키면 안 돼... 자택에서 두근두근 3SEX",
            "synopsis": "白石茉莉奈가 출연하는 이 작품은 시어머니와 아들의 비밀스러운 이야기를 다룹니다. 마지막에는 남편이 자는 옆에서 세 명이서 절정에 이릅니다."
        },
        {
            "code": "MIDV-041",
            "title": "新人OL 誘惑のオフィス 禁断の残業中 激しく乱れる",
            "synopsis": "입사 1년차 신입 OL이 부장님의 유혹에 넘어가 텅 빈 사무실에서 금단적인 관계를 맺게 됩니다."
        }
    ]

    for case in test_cases:
        print(f"\n[테스트] {case['code']}")
        print(f"  원문: {case['title']}")
        
        # 제목 번역 테스트
        ko_title = await translator.translate_title(case['code'], case['title'])
        print(f"  번역: {ko_title}")
        
        # 시놉시스 번역 테스트 (간략화)
        ko_synopsis = await translator.translate_synopsis(case['synopsis'][:50] + "...")
        print(f"  시놉: {ko_synopsis}")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
