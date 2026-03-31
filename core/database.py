"""
데이터베이스 스키마 (v8.1): 9대 핵심 정보 통합 관리 모드.
- 신규 컬럼: maker (제작사), release_date (출시일) 추가.
- 모든 메타데이터와 표지 경로(URL/로컬)를 누락 없이 저장.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

class JAVMetadata(Base):
    """JAV 메타데이터 저장을 위한 SQLAlchemy ORM 모델 (9대 핵심 정보 포함)"""
    __tablename__ = 'jav_metadata'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_code = Column(String(50), unique=True, nullable=False) # 6. 품번 (예: SSNI-123)
    title = Column(String(500), nullable=True)                    # 3. 영상 제목 (번역본)
    original_title = Column(String(500), nullable=True)           # 현지 제목
    actors = Column(Text, nullable=True)                          # 8. 배우 목록 (태그 문자열: 시라이시 마리나, ...)
    genres = Column(Text, nullable=True)                          # 7. 장르 태그 (태그 문자열: 유부녀, 3P, ...)
    maker = Column(String(200), nullable=True)                    # 9. 메이커 (제작사)
    release_date = Column(String(100), nullable=True)             # 5. 출시일 (YYYY-MM-DD 형식 권장)
    
    # 다국어 필드 (제목)
    title_en = Column(String(500), nullable=True)
    title_zh_cn = Column(String(500), nullable=True)
    title_zh_tw = Column(String(500), nullable=True)
    
    # 다국어 필드 (배우)
    actors_ko = Column(Text, nullable=True)
    actors_ja = Column(Text, nullable=True)
    actors_romaji = Column(Text, nullable=True)
    
    cover_image_url = Column(String(1000), nullable=True)         # 1. 크롤링된 표지 원본 URL
    cover_image_local_path = Column(String(1000), nullable=True)  # 2. 로컬 다운로드된 포스터 경로
    thumb_image_local_path = Column(String(1000), nullable=True)  # [신규] 로컬 썸네일 경로
    
    synopsis = Column(Text, nullable=True)                        # 4. 시놉시스 또는 작품 설명
    synopsis_en = Column(Text, nullable=True)                     # 시놉시스 (영문)
    synopsis_zh_cn = Column(Text, nullable=True)                  # 시놉시스 (중문 간체)
    synopsis_zh_tw = Column(Text, nullable=True)                  # 시놉시스 (중문 번체)
    
    # AI 부가 데이터
    scene_summaries = Column(JSON, nullable=True)                 # 씬별 요약
    character_relationships = Column(Text, nullable=True)         # 인물 관계 분석
    
    # 분석 상태 (Phase 4 핵심)
    analysis_status = Column(String(20), default='pending')       # pending, processing, done, failed

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Actress(Base):
    """배우 정보 매핑 테이블 (일어-한글-로마지)"""
    __tablename__ = "actresses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    japanese = Column(String(200), unique=True, index=True)      # 일본어 성명 (검색 키)
    korean = Column(String(200), nullable=True)                  # 한국어 성명
    romaji = Column(String(200), nullable=True)                  # 로마자 성명
    source = Column(String(100), nullable=True)                  # 데이터 출처 (manual, auto_generated 등)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Maker(Base):
    """제작사(메이커) 정보 매핑 테이블"""
    __tablename__ = "makers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    japanese = Column(String(200), unique=True, index=True)      # 일본어명 (검색 키)
    korean = Column(String(200), nullable=True)                  # 한국어명
    english = Column(String(200), nullable=True)                 # 영어명
    slug = Column(String(200), nullable=True)                    # 식별 슬러그
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Genre(Base):
    """장르 정보 매핑 테이블"""
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    japanese = Column(String(100), unique=True, index=True)      # 일본어명 (검색 키)
    korean = Column(String(100), nullable=True)                  # 한국어명
    english = Column(String(100), nullable=True)                 # 영어명
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _default_db_path() -> str:
    from core.app_config import DB_PATH
    return str(DB_PATH.resolve())


def get_engine(db_path: str | Path | None = None):
    path = db_path or _default_db_path()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{p.resolve()}", echo=False)


def get_db_session(db_path: str | Path | None = None) -> Session:
    engine = get_engine(db_path)
    # 신규 컬럼 반영을 위해 테이블 생성
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()


def upsert_jav_metadata(
    session: Session,
    *,
    product_code: str,
    title: str | None = None,
    original_title: str | None = None,
    actors: str | None = None,
    actors_ko: str | None = None,
    actors_ja: str | None = None,
    actors_romaji: str | None = None,
    genres: str | None = None,
    maker: str | None = None,
    release_date: str | None = None,
    title_en: str | None = None,
    title_zh_cn: str | None = None,
    title_zh_tw: str | None = None,
    cover_image_url: str | None = None,
    cover_image_local_path: str | None = None,
    thumb_image_local_path: str | None = None,
    synopsis: str | None = None,
    synopsis_en: str | None = None,
    synopsis_zh_cn: str | None = None,
    synopsis_zh_tw: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JAVMetadata:
    """품번 기준으로 있으면 갱신, 없으면 삽입. 9대 핵심 필드 정밀 동기화."""
    code = (product_code or "").strip()
    if not code:
        raise ValueError("product_code 비어 있음")

    row = session.query(JAVMetadata).filter_by(product_code=code).one_or_none()
    
    fields = {
        "title": title,
        "original_title": original_title,
        "title_en": title_en,
        "title_zh_cn": title_zh_cn,
        "title_zh_tw": title_zh_tw,
        "actors": actors,
        "actors_ko": actors_ko,
        "actors_ja": actors_ja,
        "actors_romaji": actors_romaji,
        "genres": genres,
        "maker": maker,
        "release_date": release_date,
        "cover_image_url": cover_image_url,
        "cover_image_local_path": cover_image_local_path,
        "thumb_image_local_path": thumb_image_local_path,
        "synopsis": synopsis,
        "synopsis_en": synopsis_en,
        "synopsis_zh_cn": synopsis_zh_cn,
        "synopsis_zh_tw": synopsis_zh_tw,
        "analysis_status": extra.get("analysis_status") if extra else None,
    }
    
    if extra:
        for k, v in extra.items():
            if hasattr(JAVMetadata, k):
                fields[k] = v

    # --- [번역/매핑 로직 추가] ---
    # 1. Maker 번역 (일본어 -> 한국어)
    if fields.get("maker"):
        m = session.query(Maker).filter_by(japanese=fields["maker"]).first()
        if m and m.korean:
            fields["maker"] = m.korean
            
    # 2. Genre 번역 (일본어 -> 한국어)
    if fields.get("genres"):
        input_genres = [g.strip() for g in fields["genres"].split(",") if g.strip()]
        translated = []
        for g_ja in input_genres:
            g_obj = session.query(Genre).filter_by(japanese=g_ja).first()
            if g_obj and g_obj.korean:
                translated.append(g_obj.korean)
            else:
                translated.append(g_ja) # 매핑 없으면 원문 유지
        fields["genres"] = ", ".join(translated)
        
    # --- [번역/매핑 끝] ---

    if row is None:
        row = JAVMetadata(product_code=code)
        session.add(row)

    for key, val in fields.items():
        if val is not None:
            setattr(row, key, val)

    try:
        session.commit()
        return row
    except Exception:
        session.rollback()
        raise
