"""애플리케이션 전역 상수 (진입점·보안·GUI 공통)."""
from pathlib import Path

APP_NAME = "JAV Story Analyzer"
APP_DISPLAY_TITLE = "JAV 스마트 분석기"

# keyring 서비스명(Windows: 자격 증명 관리자에 표시되는 이름과 유사)
KEYRING_SERVICE_NAME = APP_NAME

# keyring 계정(사용자) 키 — 여러 API를 구분할 때 계정명으로 사용
KEYRING_ACCOUNT_OPENROUTER = "openrouter_api_key"

# python-dotenv / OS 환경변수 이름
ENV_OPENROUTER_API_KEY = "OPENROUTER_API_KEY"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

DB_PATH = PROJECT_ROOT / "jav_database.db"
MEDIA_ROOT = PROJECT_ROOT / "data" / "media"

# 표지 CDN 프록시 (SNI/지역 필터 회피용 — wsrv.nl 계열 공용 프록시)
# 공식 도메인은 images.weserv.nl (wsrv.nl 표기와 동일 계열 서비스)
WESERV_IMAGE_PROXY = "https://images.weserv.nl/"

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".webm", ".mov")

# [Phase 4] 장면 분석 및 썸네일 추출 설정
SCENE_THRESHOLD = 27.0      # PySceneDetect ContentDetector 임계값 (지나치게 높지 않게 설정)
SCENE_IMG_WIDTH = 640       # 추출 썸네일 가로 해상도
SCENE_IMG_QUALITY = 80      # WebP 압축 품질 (0-100)
SCENE_MIN_COUNT = 3         # 최소 감지 씬 개수 (미달 시 정적 샘플 위주 작동)
SCENE_FALLBACK_INTERVAL = 180 # Fallback 시 추출 간격 (초 단위, 3분)
SCENE_FRAME_SKIP = 4        # 장면 분석 시 스킵할 프레임 수
SCENE_TARGET_COUNT = 24     # 최종적으로 리포트에 포함할 목표 썸네일 수 (균등 분포 보장용)

# ============================================================
# 메타데이터 및 번역 파이프라인 설정
# ============================================================
METADATA_CONFIG = {
    # title + synopsis 모두 동일한 translation 파이프라인 사용
    "title_pipeline"    : "translation",  # DeepSeek → Hermes:free → ...
    "synopsis_pipeline" : "translation",

    # Gemini는 genre/maker 크롤링 보조용으로만 명시 (현재 크롤링 우선)
    "genre_pipeline"    : "crawling",
    "maker_pipeline"    : "crawling",
}

# ============================================================
# LLM & OpenRouter 설정
# ============================================================
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_BASE_URL     = "http://localhost:11434"

# [자동 폴백 티어]
LLM_TIERS = [
    {
        "rank"        : 1,
        "name"        : "deepseek_v3",
        "model"       : "deepseek/deepseek-chat",
        "provider"    : "openrouter",
        "cost_tier"   : "low",
        "uncensored"  : False,
        "timeout"     : 45,
        "max_ctx"     : 64000,
    },
    {
        "rank"        : 2,
        "name"        : "hermes_405b_free",
        "model"       : "nousresearch/hermes-3-llama-3.1-405b:free",
        "provider"    : "openrouter",
        "cost_tier"   : "free",
        "uncensored"  : True,
        "timeout"     : 90,
        "max_ctx"     : 32000,
        "daily_limit" : 18,
    },
    {
        "rank"        : 3,
        "name"        : "hermes_70b",
        "model"       : "nousresearch/hermes-3-llama-3.1-70b",
        "provider"    : "openrouter",
        "cost_tier"   : "medium",
        "uncensored"  : True,
        "timeout"     : 60,
        "max_ctx"     : 32000,
    },
    {
        "rank"        : 4,
        "name"        : "hermes_405b_paid",
        "model"       : "nousresearch/hermes-3-llama-3.1-405b",
        "provider"   : "openrouter",
        "cost_tier"   : "high",
        "uncensored"  : True,
        "timeout"     : 120,
        "max_ctx"     : 32000,
    },
    {
        "rank"        : 5,
        "name"        : "qwen_local",
        "model"       : "qwen2.5:14b",
        "provider"    : "ollama",
        "cost_tier"   : "free",
        "uncensored"  : False,
        "timeout"     : 180,
        "max_ctx"     : 8192,
    },
]

# [수동 선택 프리셋]
MANUAL_MODEL_PRESETS = [
    {
        "id"         : "claude_sonnet",
        "label"      : "🌟 Claude 3.5 Sonnet (최고품질 / 고가 / 일부 검열)",
        "model"      : "anthropic/claude-3.5-sonnet",
        "provider"   : "openrouter",
        "note"       : "번역 품질 최상급, 성인 콘텐츠 일부 거부 가능",
        "max_ctx"    : 160000,
    },
    {
        "id"         : "deepseek",
        "label"      : "💰 DeepSeek V3     (가성비 / 빠름 / 약한 검열)",
        "model"      : "deepseek/deepseek-chat",
        "provider"   : "openrouter",
        "max_ctx"    : 64000,
    },
    {
        "id"         : "hermes_free",
        "label"      : "🆓 Hermes 405B:free (무료 / 무검열 / 느림)",
        "model"      : "nousresearch/hermes-3-llama-3.1-405b:free",
        "provider"   : "openrouter",
        "max_ctx"    : 32000,
    },
    {
        "id"         : "hermes_70b",
        "label"      : "⚡ Hermes 70B      (유료 중간 / 무검열 / 빠름)",
        "model"      : "nousresearch/hermes-3-llama-3.1-70b",
        "provider"   : "openrouter",
        "max_ctx"    : 32000,
    },
    {
        "id"         : "hermes_405b",
        "label"      : "👑 Hermes 405B     (유료 고가 / 무검열 / 최고품질)",
        "model"      : "nousresearch/hermes-3-llama-3.1-405b",
        "provider"   : "openrouter",
        "max_ctx"    : 32000,
    },
    {
        "id"         : "local",
        "label"      : "🖥️  Qwen 14B Local  (무료 / 로컬 / 3080Ti)",
        "model"      : "qwen2.5:14b",
        "provider"   : "ollama",
        "max_ctx"    : 8192,
    },
    {
        "id"         : "custom",
        "label"      : "✏️  직접 입력       (OpenRouter 모델 ID)",
        "model"      : None,
        "provider"   : "openrouter",
    },
]

# [지수 백오프 및 검열 감지 설정]
LLM_RETRY_LIMIT = 4
LLM_BACKOFF_STAGES = [2, 4, 8, 16]

LLM_REFUSAL_PATTERNS = [
    r"^i (cannot|can't|am unable to)",
    r"^(sorry|i apologize).{0,30}(cannot|unable|won't)",
    r"this (request|content) (violates|goes against)",
    r"i'm (sorry|not able).{0,20}(cannot|unable)",
]
