import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple

import cv2
from scenedetect import SceneManager, open_video, ContentDetector
from core.app_config import (
    SCENE_THRESHOLD, SCENE_IMG_WIDTH, SCENE_IMG_QUALITY,
    SCENE_MIN_COUNT, SCENE_FALLBACK_INTERVAL, SCENE_FRAME_SKIP,
    SCENE_TARGET_COUNT, MEDIA_ROOT
)
from core.database import get_db_session, upsert_jav_metadata

class SceneAnalyzer:
    """
    [Phase 4] 장면 분석 및 고속 썸네일 추출 코어.
    - [Claude 4.6 보정이 완료된 전략] 씬 감지(Content) + 균등 샘플링 병합.
    - 초반 쏠림 방지 및 전 구간 커버리지 100% 보장.
    """

    def __init__(self, video_path: str, product_code: str):
        self.video_path = Path(video_path)
        self.product_code = product_code
        self.output_dir = MEDIA_ROOT / product_code / "scenes"
        self.scenes: List[Dict[str, Any]] = []

    def _prepare_directory(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_failure(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
            print(f"[SceneAnalyzer] 에러 발생으로 인한 임시 파일 정리 완료: {self.product_code}")

    def detect_raw_scenes(self) -> Tuple[List[Tuple[float, float]], float]:
        """ContentDetector를 사용하여 실제 씬 경계(초) 리스트와 전체 길이를 반환"""
        video = open_video(str(self.video_path))
        duration = video.duration.get_seconds()
        
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=SCENE_THRESHOLD))
        
        print(f"[SceneAnalyzer] 씬 감지 시작 (임계값: {SCENE_THRESHOLD}, Skip: {SCENE_FRAME_SKIP})...")
        scene_manager.detect_scenes(video, show_progress=True, frame_skip=SCENE_FRAME_SKIP)
        scene_list = scene_manager.get_scene_list()
        
        # [(시작, 끝), ...] 형태의 초 단위 리스트 생성
        raw_scenes = [(s[0].get_seconds(), s[1].get_seconds()) for s in scene_list]
        return raw_scenes, duration

    def _deduplicate_timestamps(self, times: List[float], min_gap: float = 30.0) -> List[float]:
        """근접한 타임스탬프 중복 제거 (최소 min_gap 초 간격 보안)"""
        if not times: return []
        sorted_times = sorted(times)
        result = [sorted_times[0]]
        for t in sorted_times[1:]:
            if t - result[-1] >= min_gap:
                result.append(t)
        return result

    def _downsample_timestamps(self, times: List[float], target: int) -> List[float]:
        """균등 간격으로 목표 개수만큼 최종 선택"""
        if len(times) <= target:
            return times
        # 간격을 최대한 균등하게 선택
        step = (len(times) - 1) / (target - 1)
        indices = [int(round(i * step)) for i in range(target)]
        return [times[i] for i in indices]

    def extract_thumbnails(self, timestamps: List[float]):
        """Fast-Seeking 기반 초고속 개별 추출"""
        if not timestamps: return
        print(f"[SceneAnalyzer] 전 구간 균등 썸네일 추출 시작 (총 {len(timestamps)}개)...")
        import time
        start = time.time()

        for i, ts in enumerate(timestamps):
            output_file = self.output_dir / f"scene_{i+1:03d}.webp"
            cmd = [
                'ffmpeg', '-y', '-ss', str(round(ts, 3)), '-i', str(self.video_path),
                '-vframes', '1', '-vf', f"scale={SCENE_IMG_WIDTH}:-1",
                '-c:v', 'libwebp', '-q:v', str(SCENE_IMG_QUALITY), str(output_file)
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=False)

        print(f"[SceneAnalyzer] 추출 완료 (소요시간: {time.time() - start:.1f}s)")

    def run_analysis_only(self) -> List[Dict[str, Any]]:
        """초반 쏠림 방지 로직이 탑재된 통합 분석 프로세스"""
        self._prepare_directory()
        
        # 1. AI 기반 씬 경계 감지
        raw_scenes, duration = self.detect_raw_scenes()
        
        # 2. 강제 균등 샘플 생성 (항상 실행, 영상 전체 커버용)
        # 0초와 마지막은 제외하고 적절한 범위 내에서 추출
        interval = duration / (SCENE_TARGET_COUNT + 1)
        forced_samples = [interval * (i + 1) for i in range(SCENE_TARGET_COUNT)]
        
        # 3. 감지된 씬의 중앙점 확보
        detected_midpoints = [s[0] + (s[1] - s[0]) / 2 for s in raw_scenes]
        
        # 4. 병합 + 중복 제거 (30초 이내 근접 샘플 방지)
        all_candidates = sorted(list(set(detected_midpoints + forced_samples)))
        deduped = self._deduplicate_timestamps(all_candidates, min_gap=30.0)
        
        # 5. 최종 리포트 타겟 개수로 다운샘플링
        final_timestamps = self._downsample_timestamps(deduped, SCENE_TARGET_COUNT)
        print(f"[SceneAnalyzer] 분석 통계: 씬감지 {len(detected_midpoints)}개 | 강제샘플 {len(forced_samples)}개 | 최종 선택 {len(final_timestamps)}개")

        # 6. 실제 추출
        self.extract_thumbnails(final_timestamps)
        
        # 7. 추출된 파일과 씬 메타데이터 매핑 (가장 가까운 감지된 씬 영역 활용)
        scene_data = []
        files = sorted(list(self.output_dir.glob("*.webp")))
        
        for i, (f, ts) in enumerate(zip(files, final_timestamps)):
            # 해당 타임스탬프가 속한 씬 바운더리 찾기 (없으면 타임스탬프 기준 소구간 생성)
            start_ts, end_ts = ts - 5, ts + 5  # 기본값
            for rs_start, rs_end in raw_scenes:
                if rs_start <= ts <= rs_end:
                    start_ts, end_ts = rs_start, rs_end
                    break
            
            scene_data.append({
                "id": i+1,
                "start_time": start_ts,
                "end_time": end_ts,
                "mid_time": ts,
                "image_rel_path": f"media/{self.product_code}/scenes/{f.name}",
                "summary": ""
            })
        return scene_data

    def run(self):
        session = get_db_session()
        try:
            upsert_jav_metadata(session, product_code=self.product_code, extra={"analysis_status": "processing"})
            scene_data = self.run_analysis_only()
            upsert_jav_metadata(session, product_code=self.product_code, 
                                 extra={"analysis_status": "done", "scene_summaries": scene_data})
            print(f"[SceneAnalyzer] 분석 프로세스 완료: {self.product_code}")
        except Exception as e:
            session.rollback()
            self._cleanup_failure()
            upsert_jav_metadata(session, product_code=self.product_code, extra={"analysis_status": "failed"})
            print(f"[SceneAnalyzer] 분석 중 치명적 오류: {e}")
            raise
        finally:
            session.close()

if __name__ == "__main__":
    pass
