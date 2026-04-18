import base64
import cv2
import openai
import json
import os
import time
from .config import cfg

def _extract_frame_at_time(video_path: str, time_sec: float):
    """지정한 초 지점의 프레임을 반환 (실패 시 None)."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(time_sec * fps) if fps > 0 else 0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    return frame


def _resize_for_low_detail(frame):
    # detail=low 비용 최적화 - 512px 수준
    h, w = frame.shape[:2]
    if h <= 0 or w <= 0:
        return frame
    scale = 512 / max(h, w)
    return cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))


def _safe_shot_filename(time_sec: float) -> str:
    # 0.1초 단위로 고정(파일명 안정성)
    t10 = int(round(float(time_sec) * 10))
    return f"shot_{t10:08d}.jpg"


def encode_image_at_time(video_path: str, time_sec: float):
    """지정한 초 지점의 프레임을 Base64로 인코딩 (detail=low 최적화)"""
    frame = _extract_frame_at_time(video_path, time_sec)
    if frame is None:
        return None
    resized = _resize_for_low_detail(frame)
    _, buffer = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return base64.b64encode(buffer).decode("utf-8")

def call_vlm(video_path: str, time_sec: float, context: str, prev_state: str, api_key: str):
    """[v2.1] GPT-4o Vision API 호출 (Base64 인코딩, detail=low)"""
    base64_image = encode_image_at_time(video_path, time_sec)
    if not base64_image:
        return {"error": f"Failed to extract frame at {time_sec}s"}
        
    client = openai.OpenAI(api_key=api_key)
    
    system_prompt = """너는 JAV 영상 분석 전문가야.
제공된 이미지를 보고 현재 '장소(Position)'와 '성행위(Action)', '강도(Intensity)'를 분석해.
반드시 다음 JSON 형식으로만 응답해:
{
  "position": "장소 (예: 침대, 거실 등)",
  "action": "행위 (예: 전희, 삽입, 대화 등)",
  "intensity": "강도 (1-5)",
  "description": "상세 묘사 (1개 문장)",
  "changed": "yes/no (이전 상태와 비교하여 주요 행위가 바뀌었는지)"
}"""

    user_content = [
        {"type": "text", "text": f"Current Time: {time_sec:.1f}s\nContext: {context}\nPrevious State: {prev_state or 'None'}"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "low"}}
    ]

    try:
        response = client.chat.completions.create(
            model=cfg.vlm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=200,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        res_text = response.choices[0].message.content
        result = json.loads(res_text)
        result["t"] = time_sec
        return result
    except Exception as e:
        return {"error": str(e), "t": time_sec}

def plan_vlm_calls_v21(skeleton: dict, signal_events: list[dict]) -> list[dict]:
    """[v2.1] Mandatory 우선 할당 예산 플래닝 (최대 25회)"""
    mandatory, optional = [], []
    
    # 1. 필수(Mandatory) 이벤트 수집 (SILENT 존 진입/퇴출 시점)
    for z in skeleton["zones"]:
        if z["zone"] == "SILENT" and z["dur"] >= 60:
            # 진입 10초, 퇴출 10초 전
            mandatory.append({"t": z["start"] + 10, "conf": 0.95, "src": "silent_entry", "mandatory": True})
            mandatory.append({"t": z["end"] - 10, "conf": 0.90, "src": "silent_exit", "mandatory": True})
    
    # 2. 비필수(Optional) 이벤트 수집 (신호 분석 기반)
    for ev in signal_events:
        if ev.get("trigger_vlm") and ev["conf"] >= cfg.vlm_min_confidence:
            optional.append({"t": ev["t"], "conf": ev["conf"], "src": ev["src"], "mandatory": False})
            
    # 확신도 순 정렬
    optional.sort(key=lambda e: -e["conf"])
    
    # 3. 예산 할당 (Mandatory 우선, 남은 예산으로 Optional 채우기)
    budget = cfg.vlm_max_calls - len(mandatory)
    planned_optional = []
    
    if budget > 0:
        for ev in optional:
            if len(planned_optional) >= budget: break
            # 분석 간격 최소 cfg.vlm_min_interval_sec(45초) 보장
            too_close = any(abs(ev["t"] - p["t"]) < cfg.vlm_min_interval_sec for p in (mandatory + planned_optional))
            if not too_close:
                planned_optional.append(ev)
                
    final_plan = sorted(mandatory + planned_optional, key=lambda x: x["t"])
    print(f"[Step 3] VLM 실행 계획 수립: 필수 {len(mandatory)} | 선택 {len(planned_optional)} | 총 {len(final_plan)}회 호출 예정")
    return final_plan

def execute_vlm_strikes(
    video_path: str,
    planned_calls: list[dict],
    api_key: str,
    *,
    screenshots_dir: str | None = None,
) -> list[dict]:
    """[NEW] 서킷 브레이커가 포함된 VLM 실행 루프"""
    results = []
    prev_state = None
    consecutive_errors = 0
    
    print(f"[Step 3] VLM 정밀 타격 시작 (서킷 브레이커 한도: {cfg.vlm_circuit_breaker_limit}회)...")
    
    for i, call in enumerate(planned_calls):
        if consecutive_errors >= cfg.vlm_circuit_breaker_limit:
            print("🚨 [Circuit Breaker] VLM API 연속 에러 발생. 호출을 강제 중단합니다. (분석 중단 및 결과 보존)")
            break
            
        t_sec = float(call["t"])
        print(f"  [Strike {i+1}/{len(planned_calls)}] Time: {t_sec:.1f}s (Src: {call['src']})")
        result = call_vlm(video_path, t_sec, f"Context: {call.get('src', 'general')}", prev_state, api_key)
        
        if "error" in result:
            consecutive_errors += 1
            print(f"    ⚠ ERROR: {result['error']}")
        else:
            consecutive_errors = 0
            if "position" in result and "action" in result:
                prev_state = f"{result['position']} / {result['action']}"
                print(f"    ✅ State: {prev_state} | Changed: {result.get('changed', 'unknown')}")

            # VLM 호출 성공 시 스크린샷을 물리 파일로 저장 (프론트엔드에서 상대 경로로 참조)
            if screenshots_dir is not None:
                try:
                    os.makedirs(screenshots_dir, exist_ok=True)
                    frame = _extract_frame_at_time(video_path, t_sec)
                    if frame is not None:
                        shot_name = _safe_shot_filename(t_sec)
                        shot_path = os.path.join(screenshots_dir, shot_name)
                        ok = cv2.imwrite(shot_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                        if ok:
                            # 결과 JSON에는 절대경로를 넣지 않는다(브라우저/마스터빌더 호환성).
                            # screenshots_dir이 어디든, UI 기준으로는 마지막 폴더명(보통 'screenshots') 아래로 참조.
                            display_dir = os.path.basename(os.path.normpath(screenshots_dir)) or "screenshots"
                            result["screenshot"] = f"{display_dir}/{shot_name}".replace("\\", "/")
                except Exception:
                    pass
                
        results.append(result)
        # API 레이트 리밋 방지 1초 대기
        time.sleep(1.0)
        
    return results
