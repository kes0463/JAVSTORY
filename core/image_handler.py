import os
import shutil
from pathlib import Path
from curl_cffi import requests
from core.app_config import MEDIA_ROOT, WESERV_IMAGE_PROXY

class ImageHandler:
    """
    고정밀 표지 관리 엔진.
    - Weserv 프록시 우선 사용 (SNI 차단 우회 및 리사이징)
    - curl-cffi 기반 직접 다운로드 폴백
    - 품번별 독립 폴더 구조 관리
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://javdb.com/'
        }

    def get_product_dir(self, product_code: str) -> Path:
        """품번별 미디어 루트 디렉토리 반환 및 생성"""
        p_dir = MEDIA_ROOT / product_code
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    def download_file(self, url: str, save_path: Path, use_proxy: bool = True, width: int = None) -> bool:
        """파일 다운로드 핵심 로직 (프록시/직접 선택)"""
        target_url = url
        if use_proxy:
            # Weserv 프록시 URL 구성
            target_url = f"{WESERV_IMAGE_PROXY}?url={url}"
            if width:
                target_url += f"&w={width}&output=jpg"
            else:
                target_url += "&output=jpg"

        try:
            print(f"[ImageHandler] 다운로드 시도: {target_url}")
            resp = requests.get(target_url, headers=self.headers, impersonate="chrome120", timeout=15)
            if resp.status_code == 200:
                # 유효한 이미지인지 간단히 체크 (Content-Type 또는 매직 바이트 생략하고 일단 저장)
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                
                # 파일 크기 체크 (에러 페이지가 이미지로 위장된 경우 방어)
                if save_path.stat().st_size < 1000: # 1KB 미만은 의심스러움
                     print(f"[ImageHandler] 경고: 파일 크기가 너무 작습니다 ({save_path.stat().st_size} bytes)")
                     return False
                return True
            else:
                print(f"[ImageHandler] 실패 (상태코드: {resp.status_code}): {target_url}")
                return False
        except Exception as e:
            print(f"[ImageHandler] 에러 발생: {e}")
            return False

    def process_jav_assets(self, product_code: str, cover_url: str) -> dict:
        """
        한 번의 호출로 원본 포스터와 썸네일을 모두 처리.
        반환값: 로컬 경로 정보 딕셔너리
        """
        if not cover_url or cover_url == "이미지 누락":
            return {}

        p_dir = self.get_product_dir(product_code)
        poster_path = p_dir / "poster.jpg"
        thumb_path = p_dir / "thumb.jpg"

        results = {
            "poster_local": str(poster_path),
            "thumb_local": str(thumb_path)
        }

        # 1. 원본 포스터 (프록시 우선)
        if not poster_path.exists() or poster_path.stat().st_size == 0:
            success = self.download_file(cover_url, poster_path, use_proxy=True)
            if not success:
                print("[ImageHandler] 프록시 원본 다운로드 실패, 직접 시도합니다...")
                self.download_file(cover_url, poster_path, use_proxy=False)

        # 2. 썸네일 (Weserv 리사이징 활용)
        if not thumb_path.exists() or thumb_path.stat().st_size == 0:
            # 썸네일은 프록시 필수 (리사이징 기능 때문에)
            success = self.download_file(cover_url, thumb_path, use_proxy=True, width=300)
            if not success:
                # 프록시 실패 시 원본에서 복사 (추후 Pillow 추가 시 로컬 리사이징으로 대체 가능)
                if poster_path.exists():
                    shutil.copy(poster_path, thumb_path)
                    print("[ImageHandler] 썸네일 프록시 실패로 원본 복사 처리")

        return results

if __name__ == "__main__":
    # 간단 테스트
    handler = ImageHandler()
    test_code = "SSNI-123"
    test_url = "https://c0.jdbstatic.com/covers/6z/6z8y3.jpg" # 실제 javdb 이미지 예시
    res = handler.process_jav_assets(test_code, test_url)
    print(f"결과: {res}")
