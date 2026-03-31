import pysrt
import cv2
import numpy as np
import os
from .config import cfg

def create_text_skeleton(srt_path: str, duration: float) -> dict:
    """Whisper SRT를 분석하여 TALK/SPARSE/SILENT 존으로 밀밀도 구간 분할"""
    print(f"[Step 1] Text Skeleton 분석 시작: {os.path.basename(srt_path)}")
    subs = pysrt.open(srt_path, encoding='utf-8')
    
    # 윈도우 기반 밀도 계산
    window = cfg.density_window_sec
    step = cfg.density_step_sec
    
    raw_zones = []
    for t in np.arange(0, duration, step):
        t_end = t + window
        # 해당 구간에 걸쳐있는 모든 서브타이틀의 총 글자 수
        count = sum(len(s.text) for s in subs if s.start.ordinal/1000.0 < t_end and s.end.ordinal/1000.0 > t)
        
        if count >= cfg.talk_threshold:
            zone_type = "TALK"
        elif count >= cfg.sparse_threshold:
            zone_type = "SPARSE"
        else:
            zone_type = "SILENT"
            
        raw_zones.append({"start": t, "end": t + step, "zone": zone_type, "dur": step})

    # 인접 구간 병합
    merged = []
    if not raw_zones: return {"zones": []}
    
    curr = raw_zones[0].copy()
    for nxt in raw_zones[1:]:
        if nxt["zone"] == curr["zone"]:
            curr["end"] = nxt["end"]
            curr["dur"] = curr["end"] - curr["start"]
        else:
            merged.append(curr)
            curr = nxt.copy()
    merged.append(curr)
    
    # v2.1: 짧은 구간 조건부 교차 병합 적용
    final_zones = merge_short_zones(merged, min_duration=cfg.min_zone_duration)
    
    print(f"[Step 1] Skeleton 구축 완료: {len(final_zones)}개 존 생성")
    return {"zones": final_zones}

def merge_short_zones(zones: list[dict], min_duration: float = 60.0) -> list[dict]:
    """[v2.1] 짧은 Zone 조건부 병합 로직"""
    if len(zones) <= 1: return zones
    merged = list(zones)
    changed = True
    
    while changed:
        changed = False
        new_merged = []
        i = 0
        while i < len(merged):
            z = merged[i]
            if z["dur"] >= min_duration:
                new_merged.append(z)
                i += 1
                continue
            
            prev_z = new_merged[-1] if new_merged else None
            next_z = merged[i + 1] if i + 1 < len(merged) else None
            
            # Case 1: 양쪽이 같으면 3개를 하나로 병합
            if prev_z and next_z and prev_z["zone"] == next_z["zone"]:
                prev_z["end"] = next_z["end"]
                prev_z["dur"] = prev_z["end"] - prev_z["start"]
                i += 2
                changed = True
                continue
            
            # Case 2: 양쪽이 다르면 병합하지 않고 유지 (중요한 전환점)
            if prev_z and next_z and prev_z["zone"] != next_z["zone"]:
                new_merged.append(z)
                i += 1
                continue
            
            # Case 3: 끝단 처리 (흡수)
            if prev_z and not next_z:
                prev_z["end"] = z["end"]
                prev_z["dur"] = prev_z["end"] - prev_z["start"]
                i += 1
                changed = True
                continue
            
            new_merged.append(z)
            i += 1
        merged = new_merged
    return merged

def compute_color_signature(frame, k=3):
    """지배색 추출 및 거리 계산 (K-Means)"""
    h, w = frame.shape[:2]
    # 중앙부 타겟팅 (UI 요소 제외)
    roi = frame[int(h*0.15):int(h*0.85), int(w*0.15):int(w*0.85)]
    pixels = roi.reshape(-1, 3).astype(np.float32)
    if len(pixels) > 5000:
        indices = np.random.choice(len(pixels), 5000, replace=False)
        pixels = pixels[indices]
    
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)
    
    # 가중치 부여된 색상 벡터 생성
    weights = counts[order] / counts.sum()
    weighted = centers[order] * weights[:, np.newaxis]
    return weighted.flatten()

def get_frame_at_time(cap, time_sec, fps):
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(time_sec * fps)))
    ret, frame = cap.read()
    return frame if ret else None

def cross_validate_cuts_v21(visual_cuts: list[float], skeleton: dict, video_path: str) -> dict:
    """[v2.1] Rule 1-B 적용 교차 검증"""
    zones = skeleton["zones"]
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ❌ Error opening video for cross validation: {video_path}")
        return {"accepted": [], "ignored": [], "delegated": [], "location_changes": []}
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    accepted, ignored, delegated, location_changes = [], [], [], []
    
    print(f"[Step 1] 교차 검증 시작 (총 {len(visual_cuts)}개 시각적 컷 분석)...")
    
    for cut in visual_cuts:
        current_zone = next((z for z in zones if z["start"] <= cut < z["end"]), None)
        if not current_zone: continue
        
        boundary_dist = min(cut - current_zone["start"], current_zone["end"] - cut)
        decision = {"t": cut, "zone": current_zone["zone"]}
        
        # 1. 텍스트 경계 근처 컷은 즉시 승인
        if boundary_dist <= 30:
            decision["action"] = "ACCEPT"
            accepted.append(decision)
        # 2. 고요 존(SILENT) 내 컷은 오케스트라의 신호 분석(B)으로 위임
        elif current_zone["zone"] == "SILENT":
            decision["action"] = "DELEGATE_TO_B"
            delegated.append(decision)
        # 3. SPARSE 존은 조건부 승인 (신호 성분과 결합용)
        elif current_zone["zone"] == "SPARSE":
            decision["action"] = "ACCEPT_CONDITIONAL"
            accepted.append(decision)
        # 4. TALK 존 내 컷은 원칙적으로 무시하되, Rule 1-B(지배색)로만 부활 가능
        elif current_zone["zone"] == "TALK":
            fb = get_frame_at_time(cap, cut - 1.0, fps)
            fa = get_frame_at_time(cap, cut + 1.0, fps)
            if fb is not None and fa is not None:
                dist = float(np.linalg.norm(compute_color_signature(fb) - compute_color_signature(fa)))
                if dist > cfg.color_change_threshold:
                    decision["action"] = "ACCEPT_LOCATION_CHANGE"
                    location_changes.append(decision)
                    accepted.append(decision)
                else:
                    decision["action"] = "IGNORE"
                    ignored.append(decision)
            else:
                decision["action"] = "IGNORE"
                ignored.append(decision)
                
    cap.release()
    print(f"  └ 결과: 승인 {len(accepted)} | 무시 {len(ignored)} | 위임 {len(delegated)}")
    return {"accepted": accepted, "ignored": ignored, "delegated": delegated, "location_changes": location_changes}
