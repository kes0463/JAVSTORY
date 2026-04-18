"""
Harvest 코디네이터: 크롤 → 매핑 → 번역 → DB → 자산.

Grok 스토리 맥락 JSON: 메타 `commit` 직후 `Transcription.story_grok_module.run_story_grok_after_harvest_async`
로 `data/cache/story_context/`에 저장(자막 파이프라인과 동일 SoT).
"""
import sys
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Harvest 내부 모듈 임포트
from javstory.harvest.crawler import HybridJavCrawler
from javstory.harvest.database import get_db_session_ctx, upsert_jav_metadata, Genre, Maker
from javstory.harvest.translator import MetadataTranslator
from javstory.utils.actress_resolver import ActressResolver
from javstory.utils.assets_handler import MetadataAssetsHandler
from javstory.config.app_config import MEDIA_ROOT, story_analysis_enabled_from_env

from javstory.utils.common import log_ts as _log_ts, tagify


def log_ts(msg: str):
    _log_ts(msg, tag="Coordinator")


def _harvest_should_run_story_context(explicit: bool | None) -> bool:
    """None이면 `JAVSTORY_STORY_ANALYSIS_ENABLED`와 동일(자막 오케스트레이터 기본과 맞춤)."""
    if explicit is False:
        return False
    if explicit is True:
        return True
    return story_analysis_enabled_from_env()


async def run_crawler_for_video_path(
    video_path: str | Path,
    api_key: str | None = None,
    *,
    product_code: str | None = None,
    enable_story_context: bool | None = None,
    story_context_tier: dict[str, Any] | None = None,
    force_rebuild_story_context: bool = False,
) -> dict[str, Any]:
    """
    [Phase 1-2 통합] 영상 경로를 받아 크롤링 -> 배우 매핑 -> AI 번역 -> DB 저장 -> 자산 처리까지 수행하는 마스터 파이프라인 (Async).

    `product_code`: 폴더명 기반 품번 등 **명시적 품번**(영상 파일명과 불일치할 때).
    `video_path`가 품번 문자열 단독(파일 없음)일 때는 `product_code`와 동일하게 두면 된다.

    Grok 스토리 맥락 JSON(`enable_story_context` / env): DB 저장 직후 공통 모듈로 생성 — **구현 완료.**
    """
    path_obj = Path(video_path)
    explicit = (product_code or "").strip().upper()
    code = explicit or path_obj.stem.upper()
    
    log_ts(f"--- 하베스트 시작: {code} ---")
    
    # [수정] video_path로부터 폴더 경로 추출 (파일이면 부모, 문자열이면 그대로)
    v_path = Path(video_path)
    stored_folder_path = str(v_path.parent.resolve()) if v_path.is_file() else None
    
    crawler = HybridJavCrawler()
    resolver = ActressResolver()
    translator = MetadataTranslator(api_key=api_key)
    assets_handler = MetadataAssetsHandler()
    
    # === [사전 DB 상태 확인] ===
    needs_crawling = True
    needs_translation = True
    
    raw_title, raw_synopsis, raw_maker = "", "", ""
    raw_actors, raw_genres = [], []
    db_cover_url, db_release_date = "", ""
    original_title = ""
    trans_res = {}
    
    try:
        # [수정] 전체 과정을 try-finally로 감싸 비동기 리소스(httpx 클라이언트 등)의 확실한 해제 보장
        try:
            from javstory.harvest.database import JAVMetadata
            with get_db_session_ctx() as session:
                row = session.query(JAVMetadata).filter_by(product_code=code).first()
                if row:
                    # 1. 원본(JA) 데이터 확인
                    has_ja = all([
                        row.title_ja and row.title_ja.strip(),
                        row.synopsis_ja and row.synopsis_ja.strip(),
                        row.cover_image_url and row.cover_image_url.strip(),
                    ])
                    if has_ja and not force_rebuild_story_context:
                        needs_crawling = False
                        raw_title = row.title_ja
                        raw_synopsis = row.synopsis_ja
                        raw_maker = row.maker_ja or ""
                        raw_actors = [a.strip() for a in (row.actors_ja or "").split(",") if a.strip()]
                        raw_genres = [g.strip() for g in (row.genres_ja or "").split(",") if g.strip()]
                        raw_genres = [g.strip() for g in (row.genres_ja or "").split(",") if g.strip()]
                        db_cover_url = row.cover_image_url
                        db_release_date = row.release_date or ""
                        original_title = row.original_title or raw_title
                        log_ts(f"✅ {code} 원본 메타데이터가 완벽하여 웹 수집(크롤링)을 생략합니다.")
                    
                    # 2. 번역(KO) 데이터 확인
                    has_ko = all([
                        row.title_ko and row.title_ko.strip(),
                        row.synopsis_ko and row.synopsis_ko.strip(),
                    ])
                    if has_ja and has_ko and not force_rebuild_story_context:
                        needs_translation = False
                        log_ts(f"✅ {code} 번역 데이터가 완벽하여 AI 번역을 생략합니다.")
        except Exception as e:
            log_ts(f"⚠️ {code} 사전 DB 확인 오류: {e}")

        # 1. 크롤링 (Metadata Ingestion)
        if needs_crawling:
            res = await crawler.fetch_metadata_smart(code)
            if not res:
                log_ts(f"⚠️ {code} 크롤링 실패 (데이터 없음)")
                return {"error": "crawling_failed"}
                
            raw_actors = res.get("actors", [])
            raw_genres = res.get("genres", [])
            raw_title = res.get("title", "")
            raw_synopsis = res.get("synopsis", "")
            raw_maker = res.get("maker", "")
            db_cover_url = res.get("cover_url", "")
            db_release_date = res.get("release_date", "")
            original_title = res.get("original_title") or raw_title

        # 2. 배우/장르/제작사 해결 (Mapping)
        resolved_actors = resolver.resolve_names(raw_actors) # JA, KO, Romaji
        
        resolved_genres = _resolve_genres(raw_genres)
        resolved_maker = _resolve_maker(raw_maker)
        
        # 3. AI 다국어 번역 (LLM Translation)
        if needs_translation:
            approved_terms = {
                "ko": {
                    **{ja: ko for ja, ko in zip(resolved_actors["ja"], resolved_actors["ko"]) if ja != ko},
                    **{ja: ko for ja, ko in zip(resolved_genres["ja"], resolved_genres["ko"]) if ja != ko},
                    **({resolved_maker["ja"]: resolved_maker["ko"]} if resolved_maker["ja"] != resolved_maker["ko"] else {})
                },
                "en": {
                    **{ja: ro for ja, ro in zip(resolved_actors["ja"], resolved_actors["romaji"]) if ja != ro},
                    **{ja: en for ja, en in zip(resolved_genres["ja"], resolved_genres["en"]) if ja != en},
                    **({resolved_maker["ja"]: resolved_maker["en"]} if resolved_maker["ja"] != resolved_maker["en"] else {})
                }
            }
            
            log_ts(f"🚀 AI 다국어 번역 중...")
            trans_res = await translator.translate_metadata_batch(
                code, raw_title, raw_synopsis, 
                actors=raw_actors, genres=raw_genres, maker=raw_maker,
                approved_terms=approved_terms
            )

        # 4. DB Upsert (Persistence)
        with get_db_session_ctx() as session:
            # [4-1] 제목 & 시놉시스 (AI 결과 우선, 실패 시 원본)
            titles = {
                "title_ja": trans_res.get("title_ja", raw_title),
                "title_ko": trans_res.get("title_ko", raw_title),
                "title_en": trans_res.get("title_en", raw_title),
                "title_zh_cn": trans_res.get("title_zh_cn", raw_title),
                "title_zh_tw": trans_res.get("title_zh_tw", raw_title),
            }
            synopses = {
                "synopsis_ja": trans_res.get("synopsis_ja", raw_synopsis),
                "synopsis_ko": trans_res.get("synopsis_ko", raw_synopsis),
                "synopsis_en": trans_res.get("synopsis_en", raw_synopsis),
                "synopsis_zh_cn": trans_res.get("synopsis_zh_cn", raw_synopsis),
                "synopsis_zh_tw": trans_res.get("synopsis_zh_tw", raw_synopsis),
            }

            def merge_list(db_list: list, ai_list: list, ja_list: list) -> list:
                if not ai_list: return db_list
                if len(db_list) != len(ai_list): return ai_list
                res_list = []
                for db, ai, ja in zip(db_list, ai_list, ja_list):
                    if db != ja: res_list.append(db)
                    else: res_list.append(ai or db)
                return res_list

            ja_actors = resolved_actors["ja"]
            actors_ko = tagify(merge_list(resolved_actors["ko"], trans_res.get("actors_ko", []), ja_actors))
            actors_romaji = tagify(merge_list(resolved_actors["romaji"], trans_res.get("actors_romaji", []), ja_actors))
            actors_zh_cn = tagify(merge_list(resolved_actors["zh_cn"], trans_res.get("actors_zh_cn", []), ja_actors))
            actors_zh_tw = tagify(merge_list(resolved_actors["zh_tw"], trans_res.get("actors_zh_tw", []), ja_actors))

            ja_genres = resolved_genres["ja"]
            genres_ko = tagify(merge_list(resolved_genres["ko"], trans_res.get("genres_ko", []), ja_genres))
            genres_en = tagify(merge_list(resolved_genres["en"], trans_res.get("genres_en", []), ja_genres))
            genres_zh_cn = tagify(merge_list(resolved_genres["zh_cn"], trans_res.get("genres_zh_cn", []), ja_genres))
            genres_zh_tw = tagify(merge_list(resolved_genres["zh_tw"], trans_res.get("genres_zh_tw", []), ja_genres))

            def merge_val(db_val, ai_val, ja_val):
                if db_val and db_val != ja_val: return db_val
                return ai_val or db_val

            ja_maker = resolved_maker["ja"]
            maker_ko = merge_val(resolved_maker["ko"], trans_res.get("maker_ko"), ja_maker)
            maker_en = merge_val(resolved_maker["en"], trans_res.get("maker_en"), ja_maker)
            maker_zh_cn = merge_val(resolved_maker["zh_cn"], trans_res.get("maker_zh_cn"), ja_maker)
            maker_zh_tw = merge_val(resolved_maker["zh_tw"], trans_res.get("maker_zh_tw"), ja_maker)

            row = upsert_jav_metadata(
                session,
                product_code=code,
                merge_empty_only=True,
                **titles,
                original_title=original_title,
                **synopses,
                actors_ja=tagify(resolved_actors["ja"]),
                actors_ko=actors_ko,
                actors_romaji=actors_romaji,
                actors_zh_cn=actors_zh_cn,
                actors_zh_tw=actors_zh_tw,
                genres_ja=tagify(resolved_genres["ja"]),
                genres_ko=genres_ko,
                genres_en=genres_en,
                genres_zh_cn=genres_zh_cn,
                genres_zh_tw=genres_zh_tw,
                maker_ja=tagify(resolved_maker["ja"]),
                maker_ko=maker_ko,
                maker_en=maker_en,
                maker_zh_cn=maker_zh_cn,
                maker_zh_tw=maker_zh_tw,
                cover_image_url=db_cover_url,
                release_date=tagify(db_release_date),
                actors=tagify(resolved_actors["ja"]),
                title=titles["title_ko"],
                synopsis=synopses["synopsis_ko"],
                genres=genres_ko,
                maker=maker_ko,
                folder_path=stored_folder_path if stored_folder_path else None
            )

            # 5. 자산 처리 (Assets - 표지 다운로드 등)
            local_cover_path = await assets_handler.download_cover_image(db_cover_url, code)
            if local_cover_path:
                row.cover_image_local_path = local_cover_path

            session.commit()
            log_ts(f"✅ {code} 수집 및 DB 저장 완료 (다국어 메타 데이터 포함)")

            if _harvest_should_run_story_context(enable_story_context):
                from javstory.translation.story_grok_module import run_story_grok_after_harvest_async
                await run_story_grok_after_harvest_async(
                    product_code=code,
                    logger_func=log_ts,
                    story_context_tier=story_context_tier,
                    force_refresh=force_rebuild_story_context,
                )

            # [추가] 스냅샷 및 다이제스트 자동 추출 트리거
            if path_obj.is_file():
                try:
                    from javstory.library.stills.snapshot_queue import snapshot_queue_manager
                    from javstory.library.stills.digest_queue import digest_queue_manager
                    from javstory.config.app_config import MEDIA_ROOT

                    out_dir = Path(MEDIA_ROOT) / code / "Snapshots"
                    existing = list(out_dir.glob("snapshot_*.jpg"))
                    if len(existing) < 5: 
                        log_ts(f"📸 스냅샷 백그라운드 큐 등록 ({code})...")
                        snapshot_queue_manager.push_job(path_obj, out_dir, product_code=code)

                    digest_dir = Path(MEDIA_ROOT) / code / "digest"
                    digest_dir.mkdir(parents=True, exist_ok=True)
                    digest_path = digest_dir / "digest.mp4"
                    if not digest_path.exists():
                        log_ts(f"🎥 다이제스트 백그라운드 큐 등록 ({code})...")
                        digest_queue_manager.push_job(path_obj, digest_path, product_code=code)
                except Exception as e:
                    log_ts(f"⚠️ 추가 미디어 구성(스냅샷/다이제스트) 도중 오류: {e}")

            return {"status": "success", "product_code": code, "row_id": row.id}
    except Exception as e:
        log_ts(f"❌ {code} 처리 중 오류 발생: {e}")
        return {"error": str(e)}
    finally:
        # [핵심] 작업이 끝나면 (성공/실패 상관없이) 번역 엔진 명시적 종료
        try:
            await translator.close()
        except:
            pass

def _resolve_genres(japanese_genres: str | list) -> dict:
    """genres 마스터 테이블 매핑 (JA -> KO, EN, ZH) | 미매핑 시 pending 상태로 저장"""
    if isinstance(japanese_genres, str):
        ja_list = [g.strip() for g in japanese_genres.split(",") if g.strip()]
    else:
        ja_list = [str(g).strip() for g in (japanese_genres or []) if str(g).strip()]
        
    ko_list, en_list = [], []
    with get_db_session_ctx() as session:
        try:
            for name in ja_list:
                row = session.query(Genre).filter_by(japanese=name).first()
                if row:
                    ko_list.append(row.korean or name)   # None이면 일본어 폴백
                    en_list.append(row.english or name)  # None이면 일본어 폴백
                else:
                    # [Pending 추가] 미매핑 장르 발견 → korean/english는 NULL 유지
                    new_genre = Genre(japanese=name, korean=None, english=None, needs_review=True)
                    session.add(new_genre)
                    session.commit()
                    ko_list.append(name)  # 폴백: 일본어 원문
                    en_list.append(name)  # 폴백: 일본어 원문
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            print(f"[Coordinator] Genre Resolve Error: {e}")
    
    # ZH(중국어)는 요청에 따라 EN(영어) 필드를 그대로 사용
    return {"ja": ja_list, "ko": ko_list, "en": en_list, "zh_cn": en_list, "zh_tw": en_list}

def _resolve_maker(japanese_maker: str) -> dict:
    """makers 마스터 테이블 매핑 (JA -> KO, EN, ZH) | 미매핑 시 pending 상태로 저장"""
    name = (japanese_maker or "").strip()
    with get_db_session_ctx() as session:
        try:
            row = session.query(Maker).filter_by(japanese=name).first()
            if row:
                ko_val = row.korean or name   # None이면 일본어 폴백
                en_val = row.english or name  # None이면 일본어 폴백
                return {
                    "ja": name, "ko": ko_val, "en": en_val, "zh_cn": en_val, "zh_tw": en_val
                }
            
            # [Pending 추가] 미매핑 제작사 발견 → korean/english는 NULL 유지
            if name:
                new_maker = Maker(japanese=name, korean=None, english=None, slug=name, needs_review=True)
                session.add(new_maker)
                session.commit()
                
            return {"ja": name, "ko": name, "en": name, "zh_cn": name, "zh_tw": name}  # 폴백
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            print(f"[Coordinator] Maker Resolve Error: {e}")
            return {"ja": name, "ko": name, "en": name, "zh_cn": name, "zh_tw": name}

async def run_crawler_phase(sku_list: List[str], is_path: bool = False, loop=None):
    """배치 실행을 위한 래퍼 함수 (Async)"""
    tasks = []
    for sku in sku_list:
        # sku가 경로인지 코드인지에 따라 처리
        tasks.append(run_crawler_for_video_path(sku))
    
    results = await asyncio.gather(*tasks)
    return results

if __name__ == "__main__":
    # 간단한 테스트 실행
    asyncio.run(run_crawler_for_video_path("DASS-026"))
