import os
import sys
import time
import shutil
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULT_FACTORY_ROOT = (
    Path(os.environ.get("JAVSTORY_FACTORY_ROOT", "")).expanduser()
    if os.environ.get("JAVSTORY_FACTORY_ROOT")
    else None
)
if DEFAULT_FACTORY_ROOT is None:
    # Windows에서 "잘 안 보이는 곳" 기본값: %LOCALAPPDATA%\JAVSTORY\Factory
    local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    DEFAULT_FACTORY_ROOT = Path(local_app_data) / "JAVSTORY" / "Factory"


def factory_paths(factory_root: Path) -> tuple[Path, Path, Path, Path]:
    inbox = factory_root / "01_INBOX"
    processing = factory_root / "02_PROCESSING"
    completed = factory_root / "03_COMPLETED"
    error = factory_root / "04_ERROR"
    return inbox, processing, completed, error

POLL_INTERVAL_SEC = 30
MIN_STABLE_AGE_SEC = 5


def ensure_work_dirs(inbox: Path, processing: Path, completed: Path, error: Path) -> None:
    for p in (inbox, processing, completed, error):
        p.mkdir(parents=True, exist_ok=True)


def _is_file_stable(path: Path, *, min_age_sec: int) -> bool:
    """
    업로드/복사 중인 파일을 잡지 않기 위한 최소 안정성 체크.
    - mtime이 너무 최근이면 skip
    """
    try:
        st = path.stat()
    except FileNotFoundError:
        return False
    age = time.time() - st.st_mtime
    return age >= float(min_age_sec)


def find_ready_pairs(inbox: Path) -> list[tuple[Path, Path]]:
    """
    INBOX에서 basename이 완전히 동일한 .mp4 + .srt 쌍을 찾는다.
    - Windows 특성상 대소문자 무시 매칭
    - 파일이 너무 최근에 수정되었으면(복사 중) skip
    """
    mp4_by_stem: dict[str, Path] = {}
    srt_by_stem: dict[str, Path] = {}

    for p in inbox.iterdir():
        if not p.is_file():
            continue
        suf = p.suffix.lower()
        stem = p.stem.lower()
        if suf == ".mp4":
            mp4_by_stem[stem] = p
        elif suf == ".srt":
            srt_by_stem[stem] = p

    pairs: list[tuple[Path, Path]] = []
    for stem, mp4 in mp4_by_stem.items():
        srt = srt_by_stem.get(stem)
        if not srt:
            continue
        if not (_is_file_stable(mp4, min_age_sec=MIN_STABLE_AGE_SEC) and _is_file_stable(srt, min_age_sec=MIN_STABLE_AGE_SEC)):
            continue
        pairs.append((mp4, srt))

    # 결정적 순서(이름 기준)로 1개씩 처리하기 좋게 정렬
    pairs.sort(key=lambda t: (t[0].name.lower(), t[1].name.lower()))
    return pairs


def _safe_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        # 덮어쓰기 방지: 같은 이름이 이미 있으면 timestamp suffix
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = dst.with_name(f"{dst.stem}__{ts}{dst.suffix}")
    shutil.move(str(src), str(dst))


def claim_pair_to_processing(processing: Path, mp4: Path, srt: Path) -> Path:
    """
    중복 인식을 막기 위해 발견 즉시 PROCESSING으로 이동.
    - 각 작업은 job_dir(폴더) 단위로 관리
    """
    # 초 단위 타임스탬프는 같은 초에 2개가 들어오면 충돌(FileExistsError) 가능.
    # 마이크로초 + 충돌 시 재시도로 job_dir 유니크 보장.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    for bump in range(100):
        suffix = "" if bump == 0 else f"__{bump:02d}"
        job_name = f"{mp4.stem}__{ts}{suffix}"
        job_dir = processing / job_name
        try:
            job_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            time.sleep(0.005)
            continue
    else:
        raise RuntimeError("job_dir 생성에 반복 실패했습니다. (이름 충돌)")

    _safe_move(mp4, job_dir / mp4.name)
    _safe_move(srt, job_dir / srt.name)
    return job_dir


def run_pipeline(job_dir: Path) -> int:
    """
    subprocess.run으로 파이프라인을 '한 번에 1개씩' 실행.
    - 병렬 처리 절대 금지
    - stdout/stderr는 job_dir 로그로 저장
    """
    mp4s = list(job_dir.glob("*.mp4"))
    srts = list(job_dir.glob("*.srt"))
    if not mp4s or not srts:
        raise RuntimeError("job_dir에 mp4/srt가 없습니다.")

    video_path = mp4s[0]
    srt_path = srts[0]

    report_path = job_dir / f"{video_path.stem}_v21_report.md"
    web_out_dir = job_dir / "web"
    shots_dir = web_out_dir / "screenshots"
    web_out_dir.mkdir(parents=True, exist_ok=True)
    shots_dir.mkdir(parents=True, exist_ok=True)

    pipeline_py = PROJECT_ROOT / "core" / "scene_analysis_v2" / "pipeline.py"
    if not pipeline_py.exists():
        raise RuntimeError(f"pipeline.py를 찾을 수 없습니다: {pipeline_py}")

    cmd = [
        sys.executable,
        str(pipeline_py),
        str(video_path),
        str(srt_path),
        "--output-report-path",
        str(report_path),
        "--web-output-dir",
        str(web_out_dir),
        "--screenshots-dir",
        str(shots_dir),
    ]

    log_path = job_dir / "pipeline.log.txt"
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return int(proc.returncode)


def finalize_job(completed: Path, error: Path, job_dir: Path, exit_code: int) -> None:
    target_root = completed if exit_code == 0 else error
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / job_dir.name
    if target.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = target_root / f"{job_dir.name}__{ts}"
    shutil.move(str(job_dir), str(target))


def rebuild_master_db(factory_root: Path) -> int:
    """
    완료된 결과를 기반으로 master_db.js 재생성.
    - 실패해도 배치 공장 자체는 멈추지 않도록 exit code만 반환
    """
    script = PROJECT_ROOT / "build_master_db.py"
    if not script.exists():
        return 1
    proc = subprocess.run(
        [sys.executable, str(script), "--factory-root", str(factory_root)],
        cwd=str(PROJECT_ROOT),
    )
    return int(proc.returncode)


def main() -> None:
    global POLL_INTERVAL_SEC
    global MIN_STABLE_AGE_SEC

    parser = argparse.ArgumentParser(description="JAV Scene Analysis v2.1 Batch Runner (sequential, watchdog)")
    parser.add_argument(
        "--factory-root",
        default=str(DEFAULT_FACTORY_ROOT),
        help="워치독 공장 루트(01~04 폴더가 생성되는 위치). 기본값: LOCALAPPDATA\\JAVSTORY\\Factory",
    )
    parser.add_argument("--interval-sec", type=int, default=POLL_INTERVAL_SEC, help="INBOX 스캔 주기(초). 기본 30")
    parser.add_argument("--min-stable-age-sec", type=int, default=MIN_STABLE_AGE_SEC, help="복사 중 파일 회피용 최소 안정 시간(초). 기본 5")
    parser.add_argument("--once", action="store_true", help="1회 스캔 후 처리 가능한 작업만 모두 처리하고 종료")
    parser.add_argument(
        "--rebuild-master-db",
        action="store_true",
        help="각 작업 완료 후 build_master_db.py를 자동 실행하여 master_db.js를 갱신",
    )
    args = parser.parse_args()

    POLL_INTERVAL_SEC = int(args.interval_sec)
    MIN_STABLE_AGE_SEC = int(args.min_stable_age_sec)

    factory_root = Path(args.factory_root).expanduser().resolve()
    inbox, processing, completed, error = factory_paths(factory_root)

    ensure_work_dirs(inbox, processing, completed, error)
    print(f"[Batch] 워치독 시작. 폴링={POLL_INTERVAL_SEC}s | FACTORY_ROOT={factory_root}")
    print(f"[Batch] INBOX={inbox}")

    while True:
        try:
            pairs = find_ready_pairs(inbox)
            if not pairs:
                if args.once:
                    return
                time.sleep(POLL_INTERVAL_SEC)
                continue

            # 1번에 1개만 처리(순차) — OOM 방지 핵심
            mp4, srt = pairs[0]
            print(f"[Batch] 감지: {mp4.name} + {srt.name}")

            job_dir = claim_pair_to_processing(processing, mp4, srt)
            print(f"[Batch] PROCESSING 이동: {job_dir.name}")

            exit_code = 1
            try:
                exit_code = run_pipeline(job_dir)
            except Exception as e:
                # 파이프라인 호출 자체가 터진 경우도 로그로 남기기
                err_log = job_dir / "batch_runner_error.txt"
                with open(err_log, "w", encoding="utf-8", errors="replace") as f:
                    f.write(str(e))
                    f.write("\n")
                exit_code = 1

            finalize_job(completed, error, job_dir, exit_code)
            if exit_code == 0:
                print(f"[Batch] 완료: {job_dir.name}")
            else:
                print(f"[Batch] 실패: {job_dir.name} (exit_code={exit_code})")

            if args.rebuild_master_db:
                try:
                    rc = rebuild_master_db(factory_root)
                    if rc != 0:
                        print(f"[Batch] master_db 재빌드 실패 (exit_code={rc})")
                except Exception as e:
                    print(f"[Batch] master_db 재빌드 예외: {e}")

            # once 모드에서는 다음 작업이 없을 때 종료되므로 루프 계속
        except KeyboardInterrupt:
            print("[Batch] 종료 요청(Ctrl+C).")
            return
        except Exception as e:
            # 워치독 자체가 죽지 않도록 보호
            print(f"[Batch] 워치독 에러: {e}")
            if args.once:
                return
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()

