import json
import asyncio
import random
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI, AsyncOpenAI
import httpx

from core.app_config import (
    LLM_TIERS, LLM_BACKOFF_STAGES, LLM_REFUSAL_PATTERNS, 
    OPENROUTER_BASE_URL, OLLAMA_BASE_URL
)

class AllTiersExhaustedError(Exception):
    """모든 LLM 모델 시도가 실패했을 때 발생하는 예외"""
    pass

class JSONValidationError(Exception):
    """JSON 형식이 유효하지 않거나 스키마가 일치하지 않을 때 발생하는 예외"""
    pass

class MultiTierRouter:
    """
    [Phase 5] 5-Tier 폴백 및 비동기 순차 연동 엔진.
    - Tier 순서: DeepSeek -> Hermes Free -> Hermes 70B -> Hermes 405B -> Local Qwen
    - 비동기 호출 및 청크 단위 순차 처리 지원.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        # OpenRouter 비동기 클라이언트
        self.or_client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            timeout=httpx.Timeout(120.0, connect=5.0)
        )
        # Ollama 비동기 클라이언트
        self.ol_client = AsyncOpenAI(
            base_url=f"{OLLAMA_BASE_URL}/v1",
            api_key="ollama",
            timeout=httpx.Timeout(300.0, connect=5.0)
        )

    async def is_refusal(self, response_text: str) -> bool:
        """검열 감지 로직"""
        try:
            json.loads(response_text)
            return False
        except:
            pass

        first_part = response_text[:200].lower().strip()
        for pattern in LLM_REFUSAL_PATTERNS:
            if re.search(pattern, first_part):
                return True
        return False

    def get_backoff_delay(self, attempt: int) -> float:
        if attempt >= len(LLM_BACKOFF_STAGES):
            base = LLM_BACKOFF_STAGES[-1]
        else:
            base = LLM_BACKOFF_STAGES[attempt]
        jitter = random.uniform(0, 1)
        return float(base + jitter)

    async def call_model(self, model_cfg: Dict[str, Any], messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        """개별 모델 비동기 호출"""
        provider = model_cfg.get("provider", "openrouter")
        client = self.or_client if provider == "openrouter" else self.ol_client
        
        response = await client.chat.completions.create(
            model=model_cfg["model"],
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"} if provider == "openrouter" else None
        )
        return response.choices[0].message.content.strip()

    async def route(self, messages: List[Dict[str, str]], tier_override: Optional[Dict[str, Any]] = None) -> str:
        """
        단건 요청에 대한 5-Tier 자동 폴백 및 수동 모드 처리.
        """
        if tier_override:
            tiers_to_try = [tier_override]
        else:
            tiers_to_try = sorted(LLM_TIERS, key=lambda x: x["rank"])

        for tier in tiers_to_try:
            model_name = tier["name"]
            model_id = tier["model"]
            print(f"  [Router] 사용 중: {model_name} ({model_id})")

            for attempt in range(4):
                try:
                    content = await self.call_model(tier, messages)
                    
                    if await self.is_refusal(content):
                        if tier.get("uncensored"):
                            print(f"    ⚠️ [Refusal] 무검열 모델 {model_name} 기만적 거절. 재시도.")
                            continue
                        else:
                            print(f"    🚫 [Censored] {model_name} 검열. 다음 티어로 전환.")
                            break 

                    return content 

                except Exception as e:
                    if tier_override: # 수동 모드면 재시도 없이 즉시 에러 (사용자 지갑 보호)
                         print(f"    ❌ [Manual Mode] {model_name} 오류: {e}")
                         raise
                    
                    delay = self.get_backoff_delay(attempt)
                    print(f"    ❌ {model_name} 오류: {e} | {delay:.1f}s 후 재시도 ({attempt+1}/4)")
                    await asyncio.sleep(delay)
            
            if tier_override: # 수동 모드 실패
                 break

            print(f"  [Router] {model_name} 실패. 다음 티어로 롤백...")

        raise AllTiersExhaustedError("모든 AI 티어가 응답에 실패했거나 검열되었습니다.")

    async def process_chunks(self, chunks: List[List[Dict]], system_prompt: str, meta_context: str, tier_override: Optional[Dict] = None, sleep_sec: float = 1.0) -> List[str]:
        """
        [Phase 5 핵심] 청크 리스트를 받아 순차적으로 LLM에 전달.
        결과 리스트를 반환하며 각 호출 사이 sleep_sec 대기.
        """
        results = []
        for i, chunk in enumerate(chunks):
            print(f"  [Router] Chunk {i+1}/{len(chunks)} 처리 중...")
            
            chunk_data = json.dumps(chunk, ensure_ascii=False)
            user_prompt = f"[Metadata]\n{meta_context}\n\n[Transcript Chunk]\n{chunk_data}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.route(messages, tier_override=tier_override)
            results.append(response)
            
            if i < len(chunks) - 1 and sleep_sec > 0:
                print(f"  [Router] {sleep_sec}초 비동기 대기 (Rate Limit 방어)...")
                await asyncio.sleep(sleep_sec)
                
        return results
