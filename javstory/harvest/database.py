from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import datetime
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from javstory.config.app_config import DB_PATH as _CFG_DB_PATH

Base = declarative_base()

class JAVMetadata(Base):
    """
    JAV 작품의 메타데이터를 저장하는 메인 테이블 (스키마 v9.0)
    언어별(KO, JA, EN, ZH) 제목, 시놉시스, 배우 정보를 관리합니다.
    """
    __tablename__ = 'jav_metadata'
    
    # [1] 핵심 식별 및 인물 정보
    id = Column(Integer, primary_key=True)
    product_code = Column(String(50), unique=True, index=True)
    
    actors_ko = Column(Text, nullable=True)
    actors_ja = Column(Text, nullable=True)
    actors_romaji = Column(Text, nullable=True)
    actors_zh_cn = Column(Text, nullable=True)
    actors_zh_tw = Column(Text, nullable=True)
    
    # [2] 다국어 제목 정보
    title_ko = Column(Text, nullable=True)
    title_ja = Column(Text, nullable=True)
    title_en = Column(Text, nullable=True)
    title_zh_cn = Column(Text, nullable=True)
    title_zh_tw = Column(Text, nullable=True)
    original_title = Column(String(500), nullable=True)
    
    # [3] 다국어 시놉시스 정보
    synopsis_ko = Column(Text, nullable=True)
    synopsis_ja = Column(Text, nullable=True)
    synopsis_en = Column(Text, nullable=True)
    synopsis_zh_cn = Column(Text, nullable=True)
    synopsis_zh_tw = Column(Text, nullable=True)
    
    # [4] 분류 및 제작 정보
    genres_ko = Column(Text, nullable=True)
    genres_ja = Column(Text, nullable=True)
    genres_en = Column(Text, nullable=True)
    genres_zh_cn = Column(Text, nullable=True)
    genres_zh_tw = Column(Text, nullable=True)
    
    maker_ko = Column(String(200), nullable=True)
    maker_ja = Column(String(200), nullable=True)
    maker_en = Column(String(200), nullable=True)
    maker_zh_cn = Column(String(200), nullable=True)
    maker_zh_tw = Column(String(200), nullable=True)
    
    # [5] 자산 및 상태 정보
    cover_image_url = Column(String(1000), nullable=True)
    cover_image_local_path = Column(String(1000), nullable=True)
    thumb_image_local_path = Column(String(1000), nullable=True)
    release_date = Column(String(100), nullable=True)
    analysis_status = Column(Text, nullable=True)
    is_hardcoded = Column(Boolean, default=False)
    folder_path = Column(String(1000), nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # 레거시 호환 필드
    title = Column(String(500), nullable=True)
    synopsis = Column(Text, nullable=True)
    actors = Column(Text, nullable=True)
    genres = Column(Text, nullable=True)
    maker = Column(String(200), nullable=True)

class Actress(Base):
    """배우 정보 테이블 (actresses)"""
    __tablename__ = 'actresses'
    id = Column(Integer, primary_key=True)
    japanese = Column(String(100), unique=True, index=True)
    korean = Column(String(100), nullable=True)   # None = 아직 미입력
    romaji = Column(String(100), nullable=True)   # None = 아직 미입력
    needs_review = Column(Boolean, default=True)  # True = 수동 확인 대기 중

class Genre(Base):
    """장르 정보 테이블 (genres)"""
    __tablename__ = 'genres'
    id = Column(Integer, primary_key=True)
    japanese = Column(String(100), unique=True, index=True)
    korean = Column(String(100), nullable=True)
    english = Column(String(100), nullable=True)
    needs_review = Column(Boolean, default=True)

class Maker(Base):
    """제작사 정보 테이블 (makers)"""
    __tablename__ = 'makers'
    id = Column(Integer, primary_key=True)
    japanese = Column(String(200), unique=True, index=True)
    korean = Column(String(200), nullable=True)
    english = Column(String(200), nullable=True)
    slug = Column(String(200), nullable=True)
    needs_review = Column(Boolean, default=True)


class BackgroundCache(Base):
    """작품 단위 LLM 배경(컨텍스트) 캐시 — meta_hash로 jav_metadata 변경 시 무효화."""
    __tablename__ = "background_cache"

    product_code = Column(String(50), primary_key=True)
    background_json = Column(Text, nullable=False)
    meta_hash = Column(String(64), nullable=False)
    model_id = Column(String(200), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    expires_at = Column(DateTime, nullable=True)


# DB 연결 및 세션 관리 — `data/db/jav_database.db`
_DB = Path(_CFG_DB_PATH).resolve()
_DB.parent.mkdir(parents=True, exist_ok=True)
DB_PATH = str(_DB)
engine = create_engine(f"sqlite:///{_DB.as_posix()}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    return SessionLocal()

@contextmanager
def get_db_session_ctx():
    """
    세션 컨텍스트 매니저.
    - 예외 시 rollback
    - 항상 close
    - commit은 호출자가 명시적으로 하거나, 컨텍스트에서 직접 호출할 수 있음
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass
        raise
    finally:
        session.close()

def init_db():
    """테이블 생성 및 기존 DB 컬럼 자동 마이그레이션"""
    _DB.parent.mkdir(parents=True, exist_ok=True)
    print(f"[DB] Using database at: {DB_PATH}")
    print("[DB] Initializing tables (create_all)...")
    Base.metadata.create_all(bind=engine)
    print("[DB] Running migration checks...")
    _migrate_add_needs_review_columns()
    print("[DB] Database initialization complete.")

def _migrate_add_needs_review_columns():
    """기존 DB에 needs_review 컬럼이 없으면 자동으로 추가 (ALTER TABLE)"""
    import sqlite3
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            for table in ("actresses", "genres", "makers"):
                cols = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})")]
                if "needs_review" not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN needs_review INTEGER DEFAULT 1")
                    print(f"[DB Migration] {table}.needs_review 컬럼 추가 완료")
            
            # jav_metadata.is_hardcoded 컬럼 추가
            cols_meta = [row[1] for row in cursor.execute("PRAGMA table_info(jav_metadata)")]
            if "is_hardcoded" not in cols_meta:
                cursor.execute("ALTER TABLE jav_metadata ADD COLUMN is_hardcoded INTEGER DEFAULT 0")
                print("[DB Migration] jav_metadata.is_hardcoded 컬럼 추가 완료")
                
            # jav_metadata.folder_path 컬럼 추가
            if "folder_path" not in cols_meta:
                cursor.execute("ALTER TABLE jav_metadata ADD COLUMN folder_path TEXT")
                print("[DB Migration] jav_metadata.folder_path 컬럼 추가 완료")
                
            conn.commit()
    except Exception as e:
        print(f"[DB Migration] 마이그레이션 실패: {e}")

def upsert_jav_metadata(session, product_code, merge_empty_only=False, **kwargs):
    """기록이 있으면 업데이트, 없으면 삽입"""
    row = session.query(JAVMetadata).filter_by(product_code=product_code).one_or_none()
    
    if not row:
        row = JAVMetadata(product_code=product_code)
        session.add(row)
    
    for key, value in kwargs.items():
        if hasattr(row, key):
            if merge_empty_only:
                existing_val = getattr(row, key)
                if not existing_val or (isinstance(existing_val, str) and not existing_val.strip()):
                    setattr(row, key, value)
            else:
                setattr(row, key, value)
            
    # 레거시 필드 자동 동기화
    if 'title_ko' in kwargs:
        if not (merge_empty_only and row.title and row.title.strip()):
            row.title = kwargs['title_ko']
    if 'synopsis_ko' in kwargs:
        if not (merge_empty_only and row.synopsis and row.synopsis.strip()):
            row.synopsis = kwargs['synopsis_ko']
    if 'actors_ja' in kwargs:
        if not (merge_empty_only and row.actors and row.actors.strip()):
            row.actors = kwargs['actors_ja']
        
    # 트랜잭션 경계는 호출자가 책임진다. (여기서는 PK 할당 등 필요 시 flush만)
    session.flush()
    return row

def is_metadata_complete(product_code: str) -> bool:
    """핵심 4종 세트(품번, KO제목, 시놉시스, 장르)가 모두 존재하면 True 반환"""
    session = get_db_session()
    try:
        row = session.query(JAVMetadata).filter_by(product_code=product_code.upper()).first()
        if not row: return False
        
        # 품번은 이미 테이블에 있으므로, 나머지 3종 체크
        # title_ko, synopsis_ko, genres_ko가 모두 비어 있지 않은지 확인
        checks = [
            row.title_ko and row.title_ko.strip(),
            row.synopsis_ko and row.synopsis_ko.strip(),
            (row.genres_ko and row.genres_ko.strip()) or (row.genres and row.genres.strip())
        ]
        return all(checks)
    except Exception:
        return False
    finally:
        session.close()
