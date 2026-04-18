import json
import os
import cv2
from datetime import datetime, timedelta

def format_time(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))

def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _compute_video_meta(
    video_path: str | None,
    classified_zones: list[dict],
    *,
    web_output_dir: str | None = None,
):
    # 기본값: zone 끝값으로 duration 추정
    duration = 0.0
    for z in classified_zones or []:
        duration = max(duration, _safe_float(z.get("end", 0)))

    fps = None
    if video_path:
        cap = None
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps_val = cap.get(cv2.CAP_PROP_FPS) or 0.0
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
                if fps_val > 0 and frame_count > 0:
                    duration = max(duration, float(frame_count / fps_val))
                if fps_val > 0:
                    fps = float(fps_val)
        except Exception:
            pass
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass

    # index.html 과 같은 폴더 기준 상대 경로 (SPA에서 <video src> 용)
    src = None
    if video_path:
        ap = os.path.abspath(video_path)
        if web_output_dir:
            base = os.path.abspath(web_output_dir)
            try:
                rel = os.path.relpath(ap, base)
                src = rel.replace("\\", "/")
            except ValueError:
                src = os.path.basename(ap)
        else:
            src = os.path.basename(ap)

    return {
        "src": src,
        "duration": duration,
        "fps": fps,
    }


def _normalize_screenshot_paths_for_spa(
    classified_zones: list[dict],
    web_output_dir: str | None,
) -> None:
    """vlm_snapshots 의 screenshot 을 SPA 루트 기준 상대 경로로 통일."""
    if not web_output_dir:
        return
    base = os.path.abspath(web_output_dir)
    for z in classified_zones or []:
        for snap in z.get("vlm_snapshots") or []:
            p = snap.get("screenshot")
            if not p or not isinstance(p, str):
                continue
            if os.path.isabs(p):
                try:
                    snap["screenshot"] = os.path.relpath(p, base).replace("\\", "/")
                except Exception:
                    # 다른 드라이브 등으로 relpath 불가한 경우:
                    # 브라우저가 로컬 절대경로를 읽을 수 없으므로 파일명으로 최소 폴백
                    snap["screenshot"] = os.path.basename(p).replace("\\", "/")
            else:
                snap["screenshot"] = p.replace("\\", "/")


def assemble_final_report_v21(
    classified_zones: list[dict],
    vlm_results: list[dict],
    output_path: str,
    *,
    video_path: str | None = None,
    web_output_dir: str | None = None,
    web_database_basename: str = "web_database",
) -> str:
    """[v2.1] 분석 데이터 통합 및 마크다운 리포트 생성 + web_database.json/js 생성"""
    print(f"[Step 4] Final Report 생성 시작: {os.path.basename(output_path)}")
    
    # 1. Zone별 VLM 스냅샷 매칭 및 서브 챕터 구성
    for z in classified_zones:
        # 해당 Zone 범위 내의 VLM 결과 추출
        z["vlm_snapshots"] = sorted([vr for vr in vlm_results if z["start"] <= vr.get("t", 0) < z["end"]], key=lambda v: v.get("t", 0))
        
        sub_chapters = []
        for i, snap in enumerate(z["vlm_snapshots"]):
            if "error" in snap: continue
            
            changed = snap.get("changed", "no").lower()
            t = snap.get("t", z["start"])
            
            # [v2.1] 첫 번째 스냅샷이거나 상태가 'yes'로 바뀌었을 때 신규 챕터 생성
            if i == 0 or changed == "yes":
                sub_chapters.append({
                    "start_t": t,
                    "position": snap.get("position", "unclear"),
                    "action": snap.get("action", "unknown"),
                    "description": snap.get("description", ""),
                    "intensity": snap.get("intensity", "?"),
                    "confirmations": []
                })
            elif sub_chapters:
                # 상태가 'no'(동일)라면 이전 서브 챕터의 확인(Confirmation)으로 추가
                sub_chapters[-1]["confirmations"].append({
                    "t": t, 
                    "position": snap.get("position")
                })
        z["sub_chapters"] = sub_chapters

    _normalize_screenshot_paths_for_spa(classified_zones, web_output_dir)

    # 1.5. 웹 앱용 DB 생성 (JSON/JS)
    video_meta = _compute_video_meta(video_path, classified_zones, web_output_dir=web_output_dir)
    web_db = {
        "version": "v2.1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "video": video_meta,
        "zones": classified_zones,
        "vlm_results": vlm_results,
    }

    # 2. 마크다운 생성 본문 작성
    md = [f"# JAV Scene Analysis Report v2.1\n"]
    md.append(f"> 분석 완료 시점: {os.uname().nodename if hasattr(os, 'uname') else 'Local'}\n")
    md.append("## 🎞 전체 타임라인 분석 요약\n")

    for z in classified_zones:
        start_fmt = format_time(z["start"])
        end_fmt = format_time(z["end"])
        zone_info = f"### [{start_fmt} - {end_fmt}] {z['zone']} ZONE (Dur: {int(z['dur'])}s)\n"
        md.append(zone_info)
        
        if z["zone"] == "TALK":
             md.append("🗣 **메인 대사 중심 구간**: 인물 간의 관계 설정 및 스토리 전개가 이루어짐.\n")
        elif z["zone"] == "SILENT":
             md.append("🔞 **핵위 및 고요 구간**: 신호 분석과 VLM 타격을 통해 활동을 정밀 추적함.\n")
        elif z["zone"] == "SPARSE":
             md.append("⛅ **탐색 및 소강 구간**: 대사와 행위가 교차되는 전이 단계.\n")
             
        if z["sub_chapters"]:
            for sc in z["sub_chapters"]:
                sc_start_fmt = format_time(sc["start_t"])
                md.append(f"- **{sc_start_fmt} - [{sc['position']}] {sc['action']} (강도: {sc['intensity']})**")
                md.append(f"  - {sc['description']}")
                if sc["confirmations"]:
                    conf_times = ", ".join([format_time(c["t"]) for c in sc["confirmations"]])
                    md.append(f"  - *동일 상태 추가 확인 지점: {conf_times}*")
            md.append("\n")
        else:
            md.append("- (VLM 상세 분석 데이터 없음)\n\n")

    # 파일 저장
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # web_database.json / web_database.js — web_output_dir 지정 시 SPA 루트에, 아니면 리포트와 같은 폴더
    web_dir = os.path.abspath(web_output_dir) if web_output_dir else (os.path.dirname(output_path) or ".")
    json_path = os.path.join(web_dir, f"{web_database_basename}.json")
    js_path = os.path.join(web_dir, f"{web_database_basename}.js")

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(web_db, f, ensure_ascii=False, indent=2)
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window.JAV_DATABASE = ")
            f.write(json.dumps(web_db, ensure_ascii=False, indent=2))
            f.write(";\n")
        print(f"  └ 웹 DB 저장 완료: {json_path}")
        print(f"  └ 웹 DB 저장 완료: {js_path}")
    except Exception as e:
        print(f"  ⚠ web_database 저장 실패: {e}")
    
    print(f"  └ 보고서 저장 완료: {output_path}")
    return "\n".join(md)
