import json
import os
from datetime import timedelta

def format_time(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))

def assemble_final_report_v21(classified_zones: list[dict], vlm_results: list[dict], output_path: str) -> str:
    """[v2.1] 분석 데이터 통합 및 마크다운 리포트 생성 (Confirmations 보존)"""
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
    
    print(f"  └ 보고서 저장 완료: {output_path}")
    return "\n".join(md)
