import asyncio
import json
import keyring
from typing import Optional

from core.llm_engine import MultiTierRouter
from core.app_config import KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER, METADATA_CONFIG

class MetadataTranslator:
    """
    [Phase 5] 메타데이터(제목, 시놉시스) 전용 번역 엔진.
    - DeepSeek V3 -> Hermes fallback 파이프라인 사용.
    - 성인 콘텐츠 특화 프롬프트 적용 (검열 회피 및 로컬라이징).
    """

    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            api_key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER)
        
        self.router = MultiTierRouter(api_key) if api_key else None

    async def translate_title(self, product_code: str, japanese_title: str) -> str:
        """일본어 제목을 자연스러운 한국어 제목으로 번역"""
        if not self.router or METADATA_CONFIG.get("title_pipeline") != "translation":
            return japanese_title

        system_prompt = f"""너는 일본 성인 미디어(JAV) 전문 한국어 번역가야.
입력으로 주어지 일본어 제목을 한국 정서에 맞는 자연스러운 한국어 제목으로 의역해라.

결과는 반드시 아래의 JSON 포맷으로만 출력해라:
{{
  "translated": "번역된 제목"
}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"제목: {japanese_title}"}
        ]

        try:
            translated = await self.router.route(messages)
            return self._clean_llm_output(translated)
        except Exception as e:
            print(f"[Translator] 제목 번역 실패 ({product_code}): {e}")
            return japanese_title

    async def translate_synopsis(self, japanese_synopsis: str) -> str:
        """일본어 시놉시스를 유려한 한국어 문장으로 번역"""
        if not self.router or not japanese_synopsis or METADATA_CONFIG.get("synopsis_pipeline") != "translation":
            return japanese_synopsis

        system_prompt = """너는 일본 성인 미디어 전문 번역가야.
일본어 작품 설명을 한국어로 유려하고 생동감 있게 번역해라.

결과는 반드시 아래의 JSON 포맷으로만 출력해라:
{{
  "translated": "번역된 시놉시스"
}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"시놉시스 원문:\n{japanese_synopsis}"}
        ]

        try:
            translated = await self.router.route(messages)
            return self._clean_llm_output(translated)
        except Exception as e:
            print(f"[Translator] 시놉시스 번역 실패: {e}")
            return japanese_synopsis

    def _clean_llm_output(self, text: str) -> str:
        """JSON 형태나 불필요한 따옴표 제거"""
        text = text.strip()
        # JSON 객체인 경우 (route에서 json_object 모드일 때)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data.get("translated", data.get("title", data.get("synopsis", text)))
        except:
            pass
        
        # 앞뒤 따옴표 제거
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1]
        
        # 마크다운 태그 제거
        text = text.replace("```json", "").replace("```", "").strip()
        return text

if __name__ == "__main__":
    # 간단 테스트
    async def test():
        t = MetadataTranslator()
        res = await t.translate_title("STAR-471", "義母와 息子の秘密の関係")
        print(f"Translated: {res}")
    
    # asyncio.run(test())
    pass
