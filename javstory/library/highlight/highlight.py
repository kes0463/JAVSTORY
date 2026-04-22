from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    from ollama import generate  # type: ignore
except Exception as _e:  # pragma: no cover
    generate = None  # type: ignore
else:
    pass

_OLLAMA_INSTALL_TRIED = False


ProgressCb = Optional[Callable[[int], None]]


def _require_cv2() -> None:
    if cv2 is None:
        raise ImportError("opencv-python(cv2)이 필요합니다. pip install opencv-python 을 실행하세요.")


def _require_ollama() -> None:
    global generate, _OLLAMA_INSTALL_TRIED
    if generate is None:
        # venv에 ollama가 빠진 경우 자동 설치 1회 시도
        if not _OLLAMA_INSTALL_TRIED:
            _OLLAMA_INSTALL_TRIED = True
            try:
                import sys as _sys
                subprocess.run(
                    [_sys.executable, "-m", "pip", "install", "ollama"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=_startupinfo_hidden(),
                    check=False,
                )
                import importlib
                mod = importlib.import_module("ollama")
                generate = getattr(mod, "generate", None)
                if generate is not None:
                    return
            except Exception:
                pass

        raise ImportError("ollama python 패키지가 필요합니다. pip install ollama 을 실행하세요.")


def _startupinfo_hidden() -> object | None:
    if os.name != "nt":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return si


def _run_quiet(cmd: list[str]) -> None:
    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=_startupinfo_hidden(),
        check=False,
    )


def _clamp_percent(p: float) -> int:
    try:
        return int(max(0, min(100, round(p))))
    except Exception:
        return 0


@dataclass(frozen=True)
class HighlightParams:
    model_name: str = "blaifa/InternVL3"
    max_frames: int = 500
    min_score: int = 70
    chunk_size: int = 30
    # 분석용 프레임 추출 해상도
    analyze_resolution: str = "1280x720"
    # 최종 클립 출력 해상도 (기존 highlight.py 로직과 동일)
    output_scale: str = "840:640"
    # 인트로/엔딩 제외 비율
    start_ratio: float = 0.15
    end_exclude_sec: float = 60.0
    # 단일 구간 최대 길이 (초)
    max_segment_sec: float = 30.0


def _probe_duration_seconds(video_path: Path) -> float:
    _require_cv2()
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps and fps > 0 and total_frames and total_frames > 0:
            return float(total_frames) / float(fps)
        return 0.0
    finally:
        cap.release()


def _extract_frames_ffmpeg(
    *,
    video_path: Path,
    temp_dir: Path,
    duration_sec: float,
    params: HighlightParams,
    progress_cb: ProgressCb,
) -> list[dict]:
    start_time = max(0.0, duration_sec * float(params.start_ratio))
    usable = max(0.0, duration_sec - start_time - float(params.end_exclude_sec))
    if usable <= 1.0:
        return []
    interval = usable / float(max(1, int(params.max_frames)))

    out: list[dict] = []
    for i in range(1, int(params.max_frames) + 1):
        t = start_time + ((i - 1) * interval)
        frame_filename = temp_dir / f"f_{i:03d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-hwaccel",
            "cuda",
            "-ss",
            f"{t:.2f}",
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-s",
            str(params.analyze_resolution),
            "-f",
            "image2",
            str(frame_filename),
        ]
        _run_quiet(cmd)
        out.append({"path": str(frame_filename), "time": round(float(t), 2)})
        if progress_cb and (i % 10 == 0 or i == int(params.max_frames)):
            progress_cb(_clamp_percent((i / float(params.max_frames)) * 30.0))  # 0~30
    return out


def _parse_segments_from_ollama(raw_text: str) -> list[dict]:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return []
    try:
        data = json.loads(raw_text)
    except Exception:
        # 일부 모델은 앞뒤 텍스트를 섞을 수 있어 배열만 추출 시도
        m = re.search(r"\[[\s\S]*\]", raw_text)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except Exception:
            return []

    found: list[dict] = []
    if isinstance(data, list):
        found = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        # 유연 파싱
        if "start" in data:
            found = [data]
        else:
            # 자주 나오는 키 우선 처리 (모델별 wrapper 키 차이: objects/output/results/data/kinetic_analysis/actions 등)
            for k in ("objects", "output", "results", "result", "data", "kinetic_analysis", "actions"):
                v = data.get(k)
                if isinstance(v, list):
                    found.extend([x for x in v if isinstance(x, dict)])
            if not found:
                # fallback: 모든 value 스캔
                for v in data.values():
                    if isinstance(v, list):
                        found.extend([x for x in v if isinstance(x, dict)])
            if not found:
                # 최후의 수단: dict의 어떤 키라도 list[dict]면 모두 후보로 채택
                try:
                    for kk, vv in data.items():
                        if isinstance(vv, list) and vv and all(isinstance(x, dict) for x in vv[:5]):
                            found.extend(vv)
                except Exception:
                    pass
            if not found:
                pass
    return found


def _clean_float(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        m = re.search(r"[-+]?\d*\.\d+|\d+", val)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return 0.0
    return 0.0


def _analyze_with_ollama(
    frame_data: list[dict],
    *,
    params: HighlightParams,
    progress_cb: ProgressCb,
) -> list[dict]:
    _require_ollama()
    all_results: list[dict] = []
    chunk_size = int(params.chunk_size)
    if chunk_size <= 0:
        chunk_size = 30

    num_chunks = max(1, len(frame_data) // chunk_size) if frame_data else 0
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size
        chunk = frame_data[start_idx:end_idx]
        if not chunk:
            continue

        images_bytes = []
        time_labels = []
        for d in chunk:
            try:
                images_bytes.append(Path(str(d["path"])).read_bytes())
                time_labels.append(f"T:{d.get('time')}s")
            except Exception:
                continue

        prompt = f"""
Task: Kinetic analysis of "Body Fusion and Rhythmic Thrusting".
TIMESTAMPS: {", ".join(time_labels)}

ANALYSIS RULES:
1. Focus: Identify continuous physical fusion where the "Body Connection" is visible and active.
2. Priority: High-speed rhythmic movement and full-body interaction get the highest scores (90-100).
3. Filter: Exclude preliminary actions by giving them scores below 40.
4. Context: Ensure the entire frame sequence is analyzed for sustained action.

OUTPUT FORMAT: Return a JSON array of objects with "start", "end", "score", and "reason".
""".strip()

        try:
            resp = generate(
                model=params.model_name,
                prompt=prompt,
                images=images_bytes,
                stream=False,
                format="json",
            )
            raw = (resp or {}).get("response", "")
            found_list = _parse_segments_from_ollama(raw)
            if i == 0:
                pass
            for item in found_list:
                all_results.append(item)
        except Exception as e:
            # 실패 구간은 건너뜀 (단, 모델 없음 등 치명적 오류면 로그라도 남김)
            err_str = str(e).lower()
            if "not found" in err_str or "unauthorized" in err_str:
                # 치명적 오류일 가능성이 높음 - 일단 계속 시도하되 첫 실패만 출력할 수도 있으나
                # 여기서는 simply continue. 대신 workers에서 전체 결과를 체크할 것임.
                pass
            continue
        finally:
            if progress_cb:
                # 30~70 구간에 매핑
                progress_cb(_clamp_percent(30.0 + ((i + 1) / float(max(1, num_chunks))) * 40.0))

    return all_results


def _encode_and_merge(
    *,
    video_path: Path,
    segments: list[dict],
    temp_dir: Path,
    output_path: Path,
    params: HighlightParams,
    progress_cb: ProgressCb,
) -> Path | None:
    valid: list[dict] = []
    for res in segments:
        if not isinstance(res, dict) or "start" not in res:
            continue
        score = res.get("score", 0)
        try:
            score_i = int(float(score))
        except Exception:
            score_i = 0
        start = _clean_float(res.get("start", 0))
        end = _clean_float(res.get("end", 0))
        if end <= start:
            continue
        if (end - start) > float(params.max_segment_sec):
            end = start + float(params.max_segment_sec)
        if score_i >= int(params.min_score):
            valid.append({"start": start, "end": end, "score": score_i})

    if not valid:
        return None

    temp_dir_abs = temp_dir.resolve()
    concat_list_path = temp_dir_abs / "concat.txt"

    total = len(valid)
    with concat_list_path.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(valid):
            seg_path = (temp_dir_abs / f"seg_{i}.mp4").as_posix()
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(seg["start"]),
                "-i",
                str(video_path),
                "-t",
                str(float(seg["end"]) - float(seg["start"])),
                "-vf",
                f"scale={params.output_scale}",
                "-c:v",
                "hevc_nvenc",
                "-preset",
                "p6",
                "-rc",
                "vbr",
                "-cq",
                "25",
                "-b:v",
                "0",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                seg_path,
            ]
            _run_quiet(cmd)
            f.write(f"file '{seg_path}'\n")
            if progress_cb:
                progress_cb(_clamp_percent(70.0 + ((i + 1) / float(total)) * 25.0))  # 70~95

    merge_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c",
        "copy",
        str(output_path),
    ]
    _run_quiet(merge_cmd)

    if output_path.is_file() and output_path.stat().st_size > 1024:
        if progress_cb:
            progress_cb(100)
        return output_path
    return None


def create_highlight_video(
    *,
    product_code: str,
    video_path: Path | str,
    output_dir: Path | str,
    params: HighlightParams | None = None,
    progress_callback: ProgressCb = None,
) -> Path | None:
    """
    하이라이트 영상을 생성합니다.

    - 생성은 사용자 버튼 클릭 시에만 트리거되는 것을 전제로 합니다.
    - output_dir 아래에 `highlight.mp4`로 저장합니다.
    """
    p = HighlightParams() if params is None else params
    vp = Path(video_path)
    if not vp.is_file():
        raise FileNotFoundError(f"원본 영상을 찾을 수 없습니다: {vp}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "highlight.mp4"

    # 찌꺼기 제거
    if output_path.exists():
        try:
            output_path.unlink()
        except Exception:
            pass

    # 제품별 temp 분리(동시 실행 충돌 방지)
    run_tag = f"{(product_code or 'UNKNOWN').strip().upper()}_{int(time.time() * 1000)}"
    base_tmp = Path(tempfile.gettempdir()) / "javstory_highlight"
    temp_dir = base_tmp / run_tag
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        dur = _probe_duration_seconds(vp)
        if dur <= 0:
            raise RuntimeError("영상 길이를 파악할 수 없습니다.")

        frame_data = _extract_frames_ffmpeg(
            video_path=vp,
            temp_dir=temp_dir,
            duration_sec=dur,
            params=p,
            progress_cb=progress_callback,
        )
        if not frame_data:
            return None

        results = _analyze_with_ollama(frame_data, params=p, progress_cb=progress_callback)
        out = _encode_and_merge(
            video_path=vp,
            segments=results,
            temp_dir=temp_dir,
            output_path=output_path,
            params=p,
            progress_cb=progress_callback,
        )
        return out
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

