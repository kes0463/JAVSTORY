"""영상에서 균등 시각 프레임 추출 — equal_split과 연동."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from javstory.library.canonical.schema import LibraryCanonical, SceneEntry
from javstory.library.paths import work_library_dir
from javstory.library.stills.equal_split import equal_split_seconds
from javstory.library.stills.time_range import parse_time_range
from javstory.config.app_config import SCENE_TARGET_COUNT

if TYPE_CHECKING:
    pass

# region agent log
def _dbg_log(hypothesisId: str, location: str, message: str, data: dict) -> None:
    try:
        import json as _json, time as _time
        payload = {
            "sessionId": "fa8910",
            "runId": "snapshots",
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(_time.time() * 1000),
        }
        with open("debug-fa8910.log", "a", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion agent log

try:
    import cv2  # type: ignore
except ImportError as e:  # pragma: no cover
    cv2 = None  # type: ignore
    _CV2_IMPORT_ERROR = e
else:
    _CV2_IMPORT_ERROR = None


def _require_cv2() -> None:
    if cv2 is None:
        raise ImportError(
            "opencv-python(cv2)이 필요합니다. pip install opencv-python 을 실행하세요."
        ) from _CV2_IMPORT_ERROR


def _safe_scene_subdir(scene_id: str) -> str:
    s = (scene_id or "scene").strip()
    if not s:
        s = "scene"
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)[:120] or "scene"


def _calculate_sharpness(frame):
    """Laplacian 연산으로 이미지의 선명도 점수를 산출합니다."""
    if frame is None:
        return 0.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _hunt_sharp_frame(cap, target_ms: float, hunt_range_ms: float = 500.0, step_ms: float = 66.0):
    """
    지정된 시점 주변을 탐색하여 가장 선명한 프레임을 반환합니다.
    hunt_range_ms: 탐색 범위 (앞뒤 합계가 아님, target부터 이후 방향 위주)
    """
    best_score = -1.0
    best_frame = None
    
    # 목표 시점부터 시작하여 일정 범위를 스캔
    # (일반적으로 움직임이 많은 씬에서 선명한 찰나를 찾기 위해 앞/뒤 스캐닝)
    start_ms = max(0, target_ms - (hunt_range_ms / 4)) # 약간 앞에서부터
    for offset in range(0, int(hunt_range_ms), int(step_ms)):
        curr_ms = start_ms + offset
        cap.set(cv2.CAP_PROP_POS_MSEC, curr_ms)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
            
        score = _calculate_sharpness(frame)
        if score > best_score:
            best_score = score
            best_frame = frame.copy()
            
        # 충분히 선명한 프레임(임계값 120 이상)을 찾으면 조기 종료 (성능 최적화)
        if best_score > 120.0:
            break
            
    return best_frame


def extract_frames(
    video_path: Path | str,
    timestamps_sec: list[float],
    output_dir: Path,
    *,
    prefix: str = "still",
    quality: int = 95,
    start_index: int = 0,
) -> list[Path]:
    """
    각 timestamp(초)에서 1프레임 JPEG 저장.
    반환: 저장된 파일 경로(절대).
    """
    _require_cv2()
    vp = Path(video_path)
    if not vp.is_file():
        raise FileNotFoundError(f"영상 파일 없음: {vp}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        cap.release()
        raise OSError(f"영상을 열 수 없습니다: {vp}")

    out_paths: list[Path] = []
    ok_count = 0
    fail_count = 0
    try:
        for i, t in enumerate(timestamps_sec):
            target_ms = float(t) * 1000.0
            
            # [고도화] 선명도 기반 지능형 프레임 선령 (Sharpness Hunting)
            frame = _hunt_sharp_frame(cap, target_ms)
            
            if frame is None:
                fail_count += 1
                continue
            
            dest = output_dir / f"{prefix}_{i + start_index:03d}.jpg"
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
            cv2.imwrite(str(dest), frame, encode_params)
            if dest.is_file():
                out_paths.append(dest.resolve())
                ok_count += 1
    finally:
        cap.release()

    _dbg_log(
        "H1",
        "javstory/library/stills/extract.py:extract_frames",
        "extract_frames summary",
        {
            "video": str(vp),
            "output_dir": str(output_dir),
            "prefix": prefix,
            "timestamps": len(timestamps_sec),
            "ok": ok_count,
            "fail": fail_count,
            "first_ts": float(timestamps_sec[0]) if timestamps_sec else None,
            "last_ts": float(timestamps_sec[-1]) if timestamps_sec else None,
        },
    )
    return out_paths


def scene_time_bounds(scene: SceneEntry) -> tuple[float | None, float | None]:
    """start_sec/end_sec 우선, 없으면 time_range 파싱."""
    a, b = scene.start_sec, scene.end_sec
    if a is not None and b is not None:
        return a, b
    return parse_time_range(scene.time_range)


def extract_stills_for_scene(
    video_path: Path | str,
    scene: SceneEntry,
    work_dir: Path,
    *,
    n_stills: int = 3,
    min_gap_sec: float = 0.5,
) -> list[str]:
    """
    구간 내 equal_split 시각으로 프레임 추출.
    반환: 작품 폴더(work_dir) 기준 상대 경로 문자열(POSIX), 예: stills/scene_id/still_000.jpg
    """
    a, b = scene_time_bounds(scene)
    if a is None or b is None:
        return []

    times = equal_split_seconds(a, b, n_stills, min_gap_sec=min_gap_sec)
    if not times:
        return []

    work_dir = Path(work_dir).resolve()
    sub = work_dir / "stills" / _safe_scene_subdir(scene.scene_id)
    abs_paths = extract_frames(video_path, times, sub, prefix="still")
    rels: list[str] = []
    for p in abs_paths:
        try:
            rels.append(p.relative_to(work_dir).as_posix())
        except ValueError:
            rels.append((Path("stills") / _safe_scene_subdir(scene.scene_id) / p.name).as_posix())
    return rels


def refresh_all_stills(
    video_path: Path | str,
    state: LibraryCanonical,
    *,
    n_per_scene: int = 3,
    only_needs_refresh: bool = True,
    library_root: Path | None = None,
) -> LibraryCanonical:
    """
    씬별 스틸 재추출 후 still_paths·needs_still_refresh 갱신.
    상대 경로는 작품 폴더(work_library_dir) 기준.
    """
    _require_cv2()
    vp = Path(video_path)
    if not vp.is_file():
        raise FileNotFoundError(f"영상 파일 없음: {vp}")

    pc = (state.product_code or "").strip().upper()
    if not pc:
        raise ValueError("product_code가 비어 있습니다.")

    work = work_library_dir(pc, root=library_root)
    work.mkdir(parents=True, exist_ok=True)

    new_scenes: list[SceneEntry] = []
    for sc in state.scenes:
        if only_needs_refresh and not sc.needs_still_refresh:
            new_scenes.append(sc)
            continue

        rels = extract_stills_for_scene(
            vp,
            sc,
            work,
            n_stills=n_per_scene,
        )
        if not rels:
            new_scenes.append(
                replace(
                    sc,
                    needs_still_refresh=bool(sc.needs_still_refresh),
                )
            )
            continue

        new_scenes.append(
            replace(
                sc,
                still_paths=rels,
                needs_still_refresh=False,
            )
        )

    return replace(state, scenes=new_scenes)


def extract_snapshots_auto(
    video_path: Path | str,
    output_dir: Path | str,
    *,
    target_count: int = SCENE_TARGET_COUNT,
    prefix: str = "snapshot",
    quality: int = 85
) -> list[Path]:
    """
    영상 전체를 target_count만큼 균등 분할하여 스냅샷 추출 (하베스트/상세 뷰 공용).
    중복성 방지를 위해 기존 prefix_*.jpg 파일은 정리하지 않고, 호출 측에서 필요시 처리.
    """
    _require_cv2()
    vp = Path(video_path)
    if not vp.is_file():
        return []

    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        cap.release()
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()

    if duration <= 0:
        return []

    # 앞뒤 2% 여백 (기존 5%에서 축소하여 더 넓은 구간 커버)
    margin = duration * 0.02
    start = margin
    end = duration - margin

    if target_count > 1:
        step = (end - start) / (target_count - 1)
        timestamps = [start + (step * i) for i in range(target_count)]
    else:
        timestamps = [duration / 2]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _dbg_log(
        "H2",
        "javstory/library/stills/extract.py:extract_snapshots_auto",
        "snapshots params",
        {
            "video": str(vp),
            "output_dir": str(out_dir),
            "duration": float(duration),
            "target_count": int(target_count),
            "timestamps": int(len(timestamps)),
            "start": float(start),
            "end": float(end),
        },
    )

    # 추출 실행 (1-based 인덱싱: snapshot_001.jpg ...)
    return extract_frames(vp, timestamps, out_dir, prefix=prefix, quality=quality, start_index=1)


def suggest_snapshot_target_count(duration_sec: float) -> int:
    """
    영상 길이에 따른 스냅샷 개수 정책(12/40/70/120).

    - < 20분: 24
    - 20~60분: 70
    - 60~120분: 120
    - 120분+: 150
    """
    try:
        d = float(duration_sec)
    except Exception:
        return 24
    if d <= 0:
        return 24
    if d < 20 * 60:
        return 24
    if d < 60 * 60:
        return 70
    if d < 120 * 60:
        return 120
    return 150


def probe_video_duration_seconds(video_path: Path | str) -> float:
    """cv2로 대략 duration(sec) 계산. 실패 시 0.0."""
    _require_cv2()
    vp = Path(video_path)
    if not vp.is_file():
        return 0.0
    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        cap.release()
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps and fps > 0:
        return float(frame_count) / float(fps)
    return 0.0


def extract_snapshots_cuda(
    video_path: Path | str,
    output_dir: Path | str,
    *,
    target_count: int = 150,
    prefix: str = "snapshot",
    quality: int = 85,
    progress_callback: Optional[Callable[[int], None]] = None
) -> list[Path]:
    """
    [RTX 3080Ti 전용] 고속 시크(Fast Seek)와 병렬 처리를 이용해 스냅샷을 광속으로 추출합니다.
    사용자 제안에 따라 전체를 읽지 않고 목표 시점으로 '점프'하여 추출하므로 매우 빠르고 균등한 분할을 보장합니다.
    """
    import subprocess
    import os
    from concurrent.futures import ThreadPoolExecutor

    vp = Path(video_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    dur = probe_video_duration_seconds(vp)
    if dur <= 0: return []
    
    # 1. 타임스탬프 계산 (정밀 균등 분할)
    margin = dur * 0.02
    start = margin
    end = dur - margin
    if target_count > 1:
        step = (end - start) / (target_count - 1)
        timestamps = [start + (step * i) for i in range(target_count)]
    else:
        timestamps = [dur / 2]

    def _extract_single_frame(idx, t):
        dest = out_dir / f"{prefix}_{idx + 1:03d}.jpg"
        # -ss를 -i 앞에 두어 고속 시크를 수행
        cmd = [
            "ffmpeg", "-y",
            "-hwaccel", "auto",
            "-ss", str(round(t, 3)),
            "-i", str(vp),
            "-vframes", "1",
            "-vf", "scale=860:-2",
            "-q:v", str(min(31, max(1, int((100 - quality) / 2)))),
            "-f", "image2",
            str(dest)
        ]
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
            return dest if dest.is_file() else None
        except:
            return None

    # 3080Ti 성능을 고려하여 8개 병렬 프로세스 실행 (NVDEC 동시성 활용)
    results = []
    total = len(timestamps)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_extract_single_frame, i, t) for i, t in enumerate(timestamps)]
        for i, future in enumerate(futures):
            res = future.result()
            if res: results.append(res)
            if progress_callback:
                progress_callback(int((i + 1) / total * 100))

    if results:
        if progress_callback: progress_callback(100)
        return sorted(results)
    return []


def extract_snapshots_auto_adaptive(
    video_path: Path | str,
    output_dir: Path | str,
    *,
    prefix: str = "snapshot",
    quality: int = 85,
    progress_callback: Optional[Callable[[int], None]] = None
) -> list[Path]:
    """duration 기반 개수 정책으로 스냅샷 자동 추출."""
    dur = probe_video_duration_seconds(video_path)
    count = suggest_snapshot_target_count(dur)
    
    # [우선순위] CUDA 가속 시도
    res = extract_snapshots_cuda(video_path, output_dir, target_count=count, prefix=prefix, quality=quality, progress_callback=progress_callback)
    if res:
        return res
        
    # [Fallback] GPU 실패 시 기존 CPU(OpenCV) 방식 사용
    return extract_snapshots_auto(
        video_path,
        output_dir,
        target_count=count,
        prefix=prefix,
        quality=quality,
    )
