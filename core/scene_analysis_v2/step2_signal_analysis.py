import numpy as np
import cv2
import soundfile as sf
import subprocess
import tempfile
import os
from .config import cfg

def load_audio_segment(audio_path: str, start_sec: float, end_sec: float, target_sr: int = 16000):
    """[v2.1] 메모리 터짐 방지 오디오 로드 (Soundfile + FFmpeg Fallback)"""
    try:
        info = sf.info(audio_path)
        start_samp = int(start_sec * info.samplerate)
        end_samp = min(int(end_sec * info.samplerate), int(info.frames))
        
        y, sr = sf.read(audio_path, start=max(0, start_samp), stop=end_samp, dtype='float32')
        if y.ndim > 1: y = np.mean(y, axis=1) # Stereo to Mono
        
        # 샘플레이트가 다를 경우에만 리샘플링 실행
        if sr != target_sr:
            import librosa
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        return y, target_sr
    except Exception as e:
        print(f"  ⚠ soundfile failed: {e}. Falling back to ffmpeg sub-process.")
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            # 타겟 구간만 ffmpeg으로 잘라서 임시 WAV 생성
            cmd = [
                'ffmpeg', '-y', '-ss', str(start_sec), '-t', str(end_sec - start_sec), 
                '-i', audio_path, '-ar', str(target_sr), '-ac', '1', '-f', 'wav', tmp_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            y, sr = sf.read(tmp_path, dtype='float32')
            return y, sr
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

def analyze_motion_energy(video_path: str, start_sec: float, end_sec: float):
    """[v2.1] CPU 기반 Optical Flow (Gunnar Farneback) 분석"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 분석 구간 설정
    start_f = int(start_sec * fps)
    end_f = min(int(end_sec * fps), total_frames)
    
    # 성능을 위해 건너뜀 적용 (cfg.optical_flow_fps)
    step = int(fps / cfg.optical_flow_fps)
    if step < 1: step = 1
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    ret, prev_frame = cap.read()
    if not ret: return []
    
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    energies = []
    
    for f_idx in range(start_f + step, end_f, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret: break
        
        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Gunnar Farneback 알고리즘
        flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        energy = np.mean(mag)
        energies.append({"t": f_idx / fps, "energy": energy})
        prev_gray = curr_gray
        
    cap.release()
    return energies

def detect_motion_dips(energies: list[dict]) -> list[dict]:
    """모션 에너지가 급락하는 지점(Dip) 탐지 (장면 전환 의심)"""
    if not energies: return []
    
    energy_vals = [e["energy"] for e in energies]
    avg_energy = np.mean(energy_vals)
    dips = []
    
    # 윈도우 평균 대비 하락폭 분석
    for i in range(1, len(energies) - 1):
        e = energies[i]
        prev_e = energies[i-1]
        next_e = energies[i+1]
        
        # 주변 대비 하락률(cfg.dip_ratio) 체크
        if e["energy"] < avg_energy * cfg.dip_ratio:
            if e["energy"] < prev_e["energy"] and e["energy"] < next_e["energy"]:
                dips.append({
                    "t": e["t"], 
                    "conf": 1.0 - (e["energy"] / (avg_energy + 1e-6)),
                    "src": "motion_dip"
                })
    return dips

def analyze_audio_rhythm(y, sr):
    """오디오 리듬(BPM/Beat) 분석을 통한 행위 전환 의심 지점 확보 (가이드)"""
    import librosa
    # 메모리 효율을 위해 전체 스펙트로그램 대신 RMS 및 온셋 강도만 분석
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    # 비트 탐지 (BPM 추정 및 비트 이벤트)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    return tempo, librosa.frames_to_time(beats, sr=sr)

def orchestrate_signal_analysis(video_path: str, audio_path: str, delegated_cuts: list[dict]):
    """SILENT 존 등에 위임된 컷들에 대해 신호 분석 협업 수행"""
    print(f"[Step 2] Signal Analysis 진행 (위임된 {len(delegated_cuts)}개 이벤트)...")
    
    events = []
    for cut in delegated_cuts:
        # 컷 전후 15초(fusion_tolerance) 영역 분석
        start = max(0, cut["t"] - cfg.fusion_tolerance_sec)
        end = cut["t"] + cfg.fusion_tolerance_sec
        
        # 1. 모션 에너지 분석 (Gunnar Farneback)
        m_energies = analyze_motion_energy(video_path, start, end)
        m_dips = detect_motion_dips(m_energies)
        
        # 2. 오디오 분석 (soundfile 기반 부분 로드)
        y, sr = load_audio_segment(audio_path, start, end)
        if y is not None:
             tempo, beats = analyze_audio_rhythm(y, sr)
             # 비트 밀도가 급변하거나 BPM이 높은 구간 매칭 로직 (간소화)
             
        # 모션 Dip과 시각적 컷의 근접성 체크 (Trigger VLM 판별)
        for dip in m_dips:
            if abs(dip["t"] - cut["t"]) <= cfg.cut_exclusion_sec:
                dip["trigger_vlm"] = True
                dip["action"] = "FUSION_MATCH"
                events.append(dip)
    
    print(f"  └ 결과: 신호 기반 {len(events)}개 이벤트 탐지")
    return events
