import os
import cv2
import numpy as np
from unittest import mock
import argparse
import inspect
import io
import contextlib

from .config import cfg
from . import step1_text_skeleton as s1
from . import step2_signal_analysis as s2
from . import step3_vlm_strike as s3
from . import step4_assembly as s4


# 1) 인터페이스 검증: Step1 -> Step2 -> Step3 -> Step4 더미 릴레이
def test_interface_relay_pipeline():
    """
    Step 1 -> 2 -> 3 -> 4로 이어지는 Dict/JSON 인터페이스가
    서로 깨지지 않고 맞물리는지 더미 데이터로 빠르게 검증한다.
    """
    # Step 1 출력 형식 더미 (create_text_skeleton 결과 형식)
    skeleton = {
        "zones": [
            {"start": 0.0, "end": 60.0, "zone": "SILENT", "dur": 60.0},
            {"start": 60.0, "end": 120.0, "zone": "TALK", "dur": 60.0},
        ]
    }

    # Step 2 출력 형식 더미 (orchestrate_signal_analysis 결과 형식)
    signal_events = [
        {
            "t": 30.0,
            "energy": 0.8,
            "conf": 0.9,
            "src": "motion_dip",
            "trigger_vlm": True,
        },
        {
            "t": 90.0,
            "energy": 0.6,
            "conf": 0.8,
            "src": "motion_dip",
            "trigger_vlm": True,
        },
    ]

    # Step 3: VLM 호출 플래너
    original_budget = cfg.vlm_max_calls
    cfg.vlm_max_calls = 5  # 테스트에서는 작은 값으로 제한
    try:
        planned_calls = s3.plan_vlm_calls_v21(skeleton, signal_events)
    finally:
        cfg.vlm_max_calls = original_budget

    # 인터페이스 검증 - plan_vlm_calls_v21 결과 구조
    assert isinstance(planned_calls, list)
    assert all("t" in c and "conf" in c and "src" in c for c in planned_calls)

    # Step 4 입력 형식 더미 (실제 VLM 결과)
    dummy_vlm_results = []
    for call in planned_calls:
        dummy_vlm_results.append(
            {
                "t": call["t"],
                "position": "침대",
                "action": "전희",
                "intensity": "3",
                "description": "더미 설명",
                "changed": "yes",
            }
        )

    # Step 4: 최종 리포트 생성 (파일은 임시 경로로 생성)
    tmp_md_path = os.path.join(os.path.dirname(__file__), "tmp_qa_interface_report.md")
    md_text = s4.assemble_final_report_v21(
        classified_zones=skeleton["zones"],
        vlm_results=dummy_vlm_results,
        output_path=tmp_md_path,
    )

    assert isinstance(md_text, str)
    assert "# JAV Scene Analysis Report" in md_text
    if os.path.exists(tmp_md_path):
        os.remove(tmp_md_path)


# 2) 모듈 독립 테스트 (OpenCV / SRT / 오디오 I/O Mocking)
def test_step1_create_text_skeleton_with_mock_srt():
    """실제 SRT 파일 없이 pysrt.open 을 Mocking 해서 Step 1 로직을 단독 검증."""
    fake_subs = []

    # 단일 긴 자막 한 줄을 가진 더미 객체
    sub = mock.Mock()
    sub.start.ordinal = 0
    sub.end.ordinal = 60_000  # 60초
    sub.text = "더미 자막 텍스트입니다." * 3
    fake_subs.append(sub)

    with mock.patch.object(s1.pysrt, "open", return_value=fake_subs):
        result = s1.create_text_skeleton("dummy.srt", duration=60.0)

    assert isinstance(result, dict)
    assert "zones" in result
    assert len(result["zones"]) >= 1
    for z in result["zones"]:
        assert {"start", "end", "zone", "dur"} <= set(z.keys())


def test_step1_cross_validate_cuts_with_mock_video():
    """실제 영상 파일 없이 cv2.VideoCapture 를 Mocking 해서 교차 검증 로직을 단독 검증."""

    class DummyCap:
        def __init__(self):
            self.fps = 30.0

        def isOpened(self):
            return True

        def get(self, prop_id):
            if prop_id == cv2.CAP_PROP_FPS:
                return self.fps
            return 0

        def set(self, *_args, **_kwargs):
            return True

        def read(self):
            # 64x64 단색 더미 프레임 생성
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            return True, frame

        def release(self):
            pass

    skeleton = {
        "zones": [
            {"start": 0.0, "end": 120.0, "zone": "TALK", "dur": 120.0},
        ]
    }
    visual_cuts = [10.0, 30.0, 50.0]

    with mock.patch.object(s1.cv2, "VideoCapture", return_value=DummyCap()):
        result = s1.cross_validate_cuts_v21(
            visual_cuts=visual_cuts, skeleton=skeleton, video_path="dummy.mp4"
        )

    assert isinstance(result, dict)
    assert {"accepted", "ignored", "delegated", "location_changes"} <= set(result.keys())
    # 최소한 입력 컷 개수와 동일하거나 적은 수의 의사결정이 있어야 한다.
    total_decisions = (
        len(result["accepted"])
        + len(result["ignored"])
        + len(result["delegated"])
        + len(result["location_changes"])
    )
    assert total_decisions <= len(visual_cuts)


def test_step2_orchestrate_signal_analysis_with_mocks():
    """영상/오디오 없이 Step 2의 오케스트레이션 로직을 Mocking 기반으로 단독 검증."""

    delegated_cuts = [
        {"t": 30.0, "zone": "SILENT"},
        {"t": 90.0, "zone": "SILENT"},
    ]

    # 모션 에너지 분석 Mock: 각 컷 주변에서 하나의 dip 만 발생한다고 가정
    def fake_analyze_motion_energy(_video_path, start_sec, end_sec):
        mid = (start_sec + end_sec) / 2.0
        return [{"t": mid, "energy": 0.1}]

    # detect_motion_dips 는 실제 구현 그대로 사용해도 충분히 빠르지만,
    # 여기서는 인터페이스 확인 목적이므로 간단한 래퍼만 사용.
    def fake_detect_motion_dips(energies):
        dips = []
        for e in energies:
            dips.append(
                {
                    "t": e["t"],
                    "energy": e["energy"],
                    "conf": 0.9,
                    "src": "motion_dip",
                }
            )
        return dips

    # 오디오 로드는 None 을 반환하여 오디오 분석을 생략
    def fake_load_audio_segment(_audio_path, _s, _e, target_sr=16_000):
        return None, target_sr

    with mock.patch.object(s2, "analyze_motion_energy", side_effect=fake_analyze_motion_energy), mock.patch.object(
        s2, "detect_motion_dips", side_effect=fake_detect_motion_dips
    ), mock.patch.object(s2, "load_audio_segment", side_effect=fake_load_audio_segment):
        events = s2.orchestrate_signal_analysis(
            video_path="dummy_video.mp4",
            audio_path="dummy_audio.wav",
            delegated_cuts=delegated_cuts,
        )

    assert isinstance(events, list)
    for ev in events:
        assert {"t", "conf", "src"} <= set(ev.keys())


def test_step3_vlm_execution_with_mock_api():
    """실제 OpenAI API를 호출하지 않고 Step 3의 VLM 실행 루프를 Mocking 기반으로 검증."""

    skeleton = {
        "zones": [
            {"start": 0.0, "end": 60.0, "zone": "SILENT", "dur": 60.0},
        ]
    }
    signal_events = [
        {"t": 10.0, "conf": 0.9, "src": "motion_dip", "trigger_vlm": True},
        {"t": 40.0, "conf": 0.8, "src": "motion_dip", "trigger_vlm": True},
    ]

    original_budget = cfg.vlm_max_calls
    cfg.vlm_max_calls = 3
    try:
        planned_calls = s3.plan_vlm_calls_v21(skeleton, signal_events)
    finally:
        cfg.vlm_max_calls = original_budget

    def fake_call_vlm(_video_path, time_sec, context, prev_state, api_key):
        return {
            "t": time_sec,
            "position": "침대",
            "action": "전희",
            "intensity": "2",
            "description": f"Mock at {time_sec:.1f}s ({context})",
            "changed": "yes" if prev_state is None else "no",
        }

    with mock.patch.object(s3, "call_vlm", side_effect=fake_call_vlm), mock.patch("time.sleep", lambda *_a, **_k: None):
        # Windows 기본 콘솔(cp949)에서 Step 3의 이모지(✅/🚨) 출력이 인코딩 에러를 내는 경우가 있어,
        # stdout/stderr 를 버퍼로 돌려 테스트가 출력 인코딩에 의해 실패하지 않도록 한다.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            results = s3.execute_vlm_strikes(
                video_path="dummy_video.mp4",
                planned_calls=planned_calls,
                api_key="DUMMY_KEY",
            )

    assert isinstance(results, list)
    assert len(results) == len(planned_calls)
    for r in results:
        assert {"t", "position", "action"} <= set(r.keys())


def test_step4_assemble_final_report_minimal():
    """단순 Dict 입력으로 Step 4 리포트 생성이 정상 동작하는지 검증."""
    zones = [
        {"start": 0.0, "end": 60.0, "zone": "SILENT", "dur": 60.0},
        {"start": 60.0, "end": 120.0, "zone": "TALK", "dur": 60.0},
    ]
    vlm_results = [
        {
            "t": 10.0,
            "position": "침대",
            "action": "전희",
            "intensity": "3",
            "description": "Mock snap 1",
            "changed": "yes",
        },
        {
            "t": 20.0,
            "position": "침대",
            "action": "전희",
            "intensity": "3",
            "description": "Mock snap 2",
            "changed": "no",
        },
    ]

    tmp_md_path = os.path.join(os.path.dirname(__file__), "tmp_qa_step4_report.md")
    md_text = s4.assemble_final_report_v21(zones, vlm_results, tmp_md_path)

    assert isinstance(md_text, str)
    assert "SILENT ZONE" in md_text or "TALK ZONE" in md_text
    if os.path.exists(tmp_md_path):
        os.remove(tmp_md_path)


def _cap_vlm_calls(planned_calls: list[dict], max_calls: int) -> list[dict]:
    """Mini E2E에서 호출 수를 제한하되 시간 커버리지를 최대화."""
    if max_calls <= 0 or not planned_calls:
        return []
    if len(planned_calls) <= max_calls:
        return planned_calls

    calls_sorted = sorted(planned_calls, key=lambda c: c.get("t", 0))
    picked = [calls_sorted[0]]

    if max_calls == 1:
        return picked

    last = calls_sorted[-1]
    if last.get("t") != picked[0].get("t"):
        picked.append(last)
    else:
        # 극단 케이스: 모든 t가 동일하면 앞에서부터 채움
        for c in calls_sorted[1:]:
            if len(picked) >= max_calls:
                break
            picked.append(c)

    return sorted(picked[:max_calls], key=lambda c: c.get("t", 0))


# 3) Mini E2E: 실제 짧은 영상 & SRT를 사용하되 VLM 호출은 Mock, 호출 횟수는 최대 2회
def run_mini_e2e() -> bool:
    """
    실제 3분 내외의 짧은 영상(test_video.mp4)과 자막(test.srt)을 사용해
    파이프라인 전체를 한 번 완주해 본다.

    - VLM 호출은 최대 2회로 강제 제한
    - OpenAI API 호출과 시간 지연(time.sleep)은 Mock 으로 대체
    """
    base_dir = os.path.dirname(__file__)
    video_path = os.path.join(base_dir, "test_video.mp4")
    srt_path = os.path.join(base_dir, "test.srt")
    output_path = os.path.join(base_dir, "mini_e2e_report.md")

    assert os.path.exists(video_path), f"미니 E2E용 테스트 영상이 없습니다: {video_path}"
    assert os.path.exists(srt_path), f"미니 E2E용 테스트 SRT가 없습니다: {srt_path}"

    # --- Step 0: 영상 길이 계산 ---
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"영상 파일을 열 수 없습니다: {video_path}"
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    assert duration > 0, "영상 길이를 계산하지 못했습니다."

    # --- Step 1: 텍스트 스켈레톤 생성 ---
    skeleton = s1.create_text_skeleton(srt_path, duration=duration)
    assert "zones" in skeleton

    # 임시: 장면 전환 후보 타임스탬프를 균등 샘플링으로 생성
    visual_cuts = []
    step_sec = max(10.0, duration / 6.0)
    t = 0.0
    while t < duration:
        visual_cuts.append(t)
        t += step_sec

    cross = s1.cross_validate_cuts_v21(
        visual_cuts=visual_cuts,
        skeleton=skeleton,
        video_path=video_path,
    )
    delegated_cuts = cross.get("delegated", [])

    # --- Step 2: 신호 분석 (오디오 로드는 Mock 으로 안전하게 대체) ---
    def fake_load_audio_segment(_audio_path, _s, _e, target_sr=16_000):
        # Mini E2E에서는 오디오 분석을 스킵하여 ffmpeg / soundfile 의존성 리스크를 제거
        return None, target_sr

    with mock.patch.object(s2, "load_audio_segment", side_effect=fake_load_audio_segment):
        signal_events = s2.orchestrate_signal_analysis(
            video_path=video_path,
            audio_path=video_path,  # 실제 오디오는 사용하지 않음 (Mock 처리)
            delegated_cuts=delegated_cuts,
        )

    # --- Step 3: VLM 호출 계획 및 Mock 실행 (최대 2회) ---
    original_budget = cfg.vlm_max_calls
    cfg.vlm_max_calls = min(2, cfg.vlm_max_calls)
    try:
        planned_calls = s3.plan_vlm_calls_v21(skeleton, signal_events)
    finally:
        cfg.vlm_max_calls = original_budget

    # Step 3 플래너는 "Mandatory(필수)"를 예산보다 우선시하므로,
    # SILENT 존이 많으면 planned_calls가 2회를 초과할 수 있다.
    # Mini E2E 요구사항(최대 2회 호출)을 테스트에서 강제하되,
    # 단순히 앞에서 자르지 않고 시간 커버리지가 최대가 되게 선택한다.
    planned_calls = _cap_vlm_calls(planned_calls, max_calls=2)
    assert len(planned_calls) <= 2

    def fake_call_vlm(_video_path, time_sec, context, prev_state, api_key):
        return {
            "t": time_sec,
            "position": "침대",
            "action": "전희",
            "intensity": "2",
            "description": f"[MiniE2E Mock] {time_sec:.1f}s ({context})",
            "changed": "yes" if prev_state is None else "no",
        }

    with mock.patch.object(s3, "call_vlm", side_effect=fake_call_vlm), mock.patch("time.sleep", lambda *_a, **_k: None):
        # Windows 기본 콘솔(cp949)에서 Step 3 이모지 출력이 인코딩 에러를 내는 경우가 있어 출력은 버퍼로 우회
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            vlm_results = s3.execute_vlm_strikes(
                video_path=video_path,
                planned_calls=planned_calls,
                api_key="DUMMY_KEY",
            )

    # --- Step 3 QA: VLM 결과 최소 품질 체크 ---
    assert isinstance(vlm_results, list)
    assert 0 < len(vlm_results) <= 2, f"VLM 결과 수가 기대와 다릅니다: {len(vlm_results)}"
    assert all("error" not in r for r in vlm_results), f"VLM 결과에 error가 포함됨: {vlm_results}"
    required_vlm_keys = {"t", "position", "action", "intensity", "description", "changed"}
    for r in vlm_results:
        missing = required_vlm_keys - set(r.keys())
        assert not missing, f"VLM 결과 키 누락: missing={sorted(missing)} result={r}"

    # --- Step 4: 최종 리포트 생성 ---
    md_text = s4.assemble_final_report_v21(
        classified_zones=skeleton["zones"],
        vlm_results=vlm_results,
        output_path=output_path,
    )
    assert isinstance(md_text, str)
    assert os.path.exists(output_path)

    # --- Step 4 QA: 리포트 품질 체크 ---
    # 1) 기본 헤더/섹션 존재
    assert "# JAV Scene Analysis Report" in md_text
    assert "## 🎞 전체 타임라인 분석 요약" in md_text

    # 2) 존이 최소 1개 이상 생성
    assert isinstance(skeleton.get("zones"), list) and len(skeleton["zones"]) > 0

    # 3) VLM 스냅샷이 최소 1개 이상 리포트에 반영되었는지 (굵은 항목 형태)
    assert md_text.count("- **") >= 1, "리포트에 VLM 스냅샷 항목이 없습니다."

    # 4) (권장 품질) 2회 호출이면 서로 다른 존에 분산되었는지 확인
    if len(vlm_results) >= 2:
        zones = skeleton["zones"]

        def zone_index_for_time(t: float) -> int | None:
            for i, z in enumerate(zones):
                if z["start"] <= t < z["end"]:
                    return i
            return None

        z_ids = [zone_index_for_time(float(r["t"])) for r in vlm_results]
        assert all(z is not None for z in z_ids), f"VLM t가 어떤 zone에도 매칭되지 않음: {z_ids}"
        assert len(set(z_ids)) >= 2, f"VLM 스냅샷이 한 zone에만 몰렸습니다: zone_ids={z_ids}"

    return True


def test_mini_e2e_runs_without_error():
    """
    pytest에서 Mini E2E를 한 번 실행해 본다.
    실제 영상/자막 파일이 없으면 AssertionError 로 실패하게 된다.
    """
    assert run_mini_e2e() is True


def run_all_tests(include_mini_e2e: bool = False) -> None:
    """
    pytest 없이도 실행 가능한 간단 러너.
    - include_mini_e2e=False: unit/interface 테스트만 실행(기본값)
    - include_mini_e2e=True: Mini E2E까지 포함
    """
    current_module = globals()
    test_fns = []

    for name, obj in current_module.items():
        if not callable(obj):
            continue
        if not name.startswith("test_"):
            continue
        if (not include_mini_e2e) and name == "test_mini_e2e_runs_without_error":
            continue
        # 모듈 레벨 함수만 대상으로 제한(클래스/기타 객체 방지)
        if inspect.isfunction(obj) and obj.__module__ == __name__:
            test_fns.append(obj)

    test_fns.sort(key=lambda fn: fn.__name__)
    failures = []

    for fn in test_fns:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except Exception as e:
            failures.append((fn.__name__, e))
            print(f"[FAIL] {fn.__name__}: {e}")

    if failures:
        names = ", ".join(n for n, _ in failures)
        raise SystemExit(f"{len(failures)} test(s) failed: {names}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mini-e2e",
        action="store_true",
        help="test_video.mp4/test.srt를 이용한 Mini E2E까지 포함해서 실행",
    )
    args = parser.parse_args()

    run_all_tests(include_mini_e2e=args.mini_e2e)
    if args.mini_e2e:
        print("[Mini E2E] completed: True")
    else:
        print("[QA] unit/interface tests completed: True")

