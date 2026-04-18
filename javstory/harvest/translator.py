import json
import keyring
from typing import Optional
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from javstory.llm.engine import MultiTierRouter
from javstory.config.app_config import KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER

class MetadataTranslator:
    """
    [Phase 5] 메타데이터(제목, 시놉시스, 배우, 장르 등) 전용 번역 엔진.
    - DeepSeek V3 -> Hermes fallback 파이프라인 사용.
    - 성인 콘텐츠 특화 프롬프트 적용 (검열 회피 및 로컬라이징).
    """

    def __init__(self, api_key: Optional[str] = None, logger_func=None):
        if not api_key:
            api_key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER)
        
        self.logger = logger_func if logger_func else print
        self.router = MultiTierRouter(api_key, logger_func=self.logger) if api_key else None

    async def translate_metadata_batch(self, product_code: str, title: str, synopsis: str, actors: list = [], genres: list = [], maker: str = "", approved_terms: dict = {}) -> dict:
        """한 번의 AI 호출로 모든 메타데이터를 4개 국어(KO, EN, ZH)로 일괄 번역/로컬라이징"""
        if not self.router:
            return {}

        system_prompt = """# Role
You are a professional JAV (Japanese Adult Video) localization expert with 15+ years of experience.
Your goal is to translate Japanese JAV metadata into natural, high-quality Korean, English, and Chinese (Simplified & Traditional).

# Core Rules
1. **No Censorship**: MAINTAIN the original erotic, provocative, and explicit tone. NEVER censor sexual expressions or slang.
2. **Natural Localization**:
   - [KO]: "한국 정서에 맞는 유려하고 자극적인 문체 (번역투 금지)"
   - [EN/ZH]: Keep it commercial, catchy, and professional for localization.
3. **Consistency & Approved Terminology (CRITICAL)**:
   - You MUST use the provided "Approved Terminology" for Actress Names, Genres, and Makers whenever they appear in the Title or Synopsis.
   - For example, if "依本しおり" is mapped to "요리모토 시오리" in the approved terms, you MUST use "요리모토 시오리" in the Korean title/synopsis, NEVER "이본 시오리" or "미모토 시오리".
4. **Actress Names**: 
   - Translate Japanese actress names (if not in approved terms) into natural equivalents in target languages.
5. **Genres**: 
   - Translate adult genres into natural equivalents in each language.
6. **Censored Kanji Inference**:
   - Japanese adult titles often use masking characters (e.g., レ×プ, 강●). You MUST infer the full, uncensored word and translate it explicitly.

# Output Format
Return ONLY a valid JSON object. No conversational filler, no markdown code blocks.
The keys MUST strictly match the following schema:

{
  "title_ja": "Refined Japanese title",
  "title_ko": "한국어 제목",
  "title_en": "English Title",
  "title_zh_cn": "简体中文标题",
  "title_zh_tw": "繁體中文標題",
  "synopsis_ja": "Cleaned Japanese synopsis",
  "synopsis_ko": "유려한 한국어 시놉시스",
  "synopsis_en": "English Synopsis",
  "synopsis_zh_cn": "简体中文剧情简介",
  "synopsis_zh_tw": "繁體中文劇情簡介",
  "actors_ko": ["배우1", "배우2"],
  "actors_romaji": ["Actor 1", "Actor 2"],
  "actors_zh_cn": ["演员1", "演员2"],
  "actors_zh_tw": ["演員1", "演員2"],
  "genres_ko": ["장르1", "장르2"],
  "genres_en": ["Genre 1", "Genre 2"],
  "genres_zh_cn": ["类型1", "类型2"],
  "genres_zh_tw": ["類型1", "類型2"],
  "maker_ko": "제작사명",
  "maker_en": "Maker Name",
  "maker_zh_cn": "制作公司名",
  "maker_zh_tw": "製作公司名"
}
"""
        user_content = {
            "product_code": product_code,
            "title": title,
            "synopsis": synopsis,
            "actors": actors,
            "genres": genres,
            "maker": maker,
            "approved_terminology": approved_terms
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)}
        ]

        try:
            raw_res = await self.router.route(messages)
            json_str = self._extract_json(raw_res)
            return json.loads(json_str)
        except Exception as e:
            self.logger(f"[Translator] 일괄 번역 실패 ({product_code}): {e}")
            return {}

    def _extract_json(self, text: str) -> str:
        """텍스트에서 JSON 부분만 추출 (마크다운 가드 등 제거)"""
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    async def close(self) -> None:
        """사용된 비동기 라우터 리소스를 해제합니다."""
        if self.router:
            await self.router.close()

