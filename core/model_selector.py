"""
[Phase 5] 사용자 모델 선택 대화형 CLI 모듈.
자동 폴백 모드와 수동 프리미엄 선택 모드를 지원합니다.
"""
import sys
from core.app_config import MANUAL_MODEL_PRESETS

def select_model_interactive() -> dict:
    """수동 모드: 사용자 모델 선택 CLI"""

    print("\n" + "=" * 60)
    print("  🚀 하이엔드 AI 분석 모델 선택")
    print("=" * 60)

    # 섹션별 그룹화 출력 (시각적 도움)
    print("\n  ✨ 프리미엄 (최애 작품 전용 / 고품질)")
    for i, preset in enumerate(MANUAL_MODEL_PRESETS[:1], 1):
        print(f"    {i}. {preset['label']}")
        print(f"       └─ {preset.get('note', '')}")

    print("\n  🤖 일반 모델 (자동 폴백 티어와 동일)")
    for i, preset in enumerate(MANUAL_MODEL_PRESETS[1:-1], 2):
        print(f"    {i}. {preset['label']}")

    print("\n  ⚙️  기타")
    custom_idx = len(MANUAL_MODEL_PRESETS)
    print(f"    {custom_idx}. {MANUAL_MODEL_PRESETS[-1]['label']}")

    print("\n" + "=" * 60)
    print("  번호를 선택하거나 OpenRouter 모델 ID를 직접 입력하세요.")
    print("  예) anthropic/claude-3.5-sonnet")
    print("=" * 60)

    while True:
        try:
            choice = input("\n  선택 (기본값: 2): ").strip()
            
            if not choice:
                return MANUAL_MODEL_PRESETS[1] # 기본값: DeepSeek

            # 번호 선택 시
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(MANUAL_MODEL_PRESETS):
                    preset = MANUAL_MODEL_PRESETS[idx]

                    # 직접 입력 선택 시
                    if preset["id"] == "custom":
                        model_id = input("  👉 OpenRouter 모델 ID 입력: ").strip()
                        if not model_id:
                            print("     ⚠️ 모델 ID가 입력되지 않았습니다. 다시 선택해 주세요.")
                            continue
                        return {
                            "id"      : "custom",
                            "model"   : model_id,
                            "provider": "openrouter",
                            "max_ctx" : 32000,
                        }
                    return preset
                else:
                    print(f"     ⚠️ 잘못된 번호({choice})입니다. 리스트에 있는 번호를 입력해 주세요.")
                    continue

            # 모델 ID 직접 입력 시 (슬래시 포함 여부로 간단히 모델 ID로 판단)
            if "/" in choice:
                return {
                    "id"      : "custom",
                    "model"   : choice,
                    "provider": "openrouter",
                    "max_ctx" : 32000,
                }
            else:
                print(f"     ⚠️ 리스트 번호 또는 '전달자/모델' 형식의 ID를 입력해 주세요.")
                continue

        except KeyboardInterrupt:
            print("\n\n  👋 선택이 취소되었습니다. 프로그램을 종료합니다.")
            sys.exit(0)
        except Exception as e:
            print(f"\n  ⚠️ 오류 발생: {e}. 다시 시도해 주세요.")
            continue

if __name__ == "__main__":
    selected = select_model_interactive()
    print(f"\n✅ 선택된 모델: {selected['model']} (Provider: {selected['provider']})")
