import os
import sys
import gc
import re
import torch
import ffmpeg
import numpy as np
import librosa
from typing import List, Dict, Any, Optional

# =========================
# CUDA 11 DLL Injection (Windows)
# =========================
if sys.platform == "win32":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_base = os.path.join(root_dir, "venv")
    if os.path.exists(venv_base):
        site_packages = os.path.join(venv_base, "Lib", "site-packages")
        nvidia_base = os.path.join(site_packages, "nvidia")
        if os.path.exists(nvidia_base):
            for sub in ["cublas", "cudnn"]:
                dll_path = os.path.join(nvidia_base, sub, "bin")
                if os.path.exists(dll_path):
                    try:
                        os.add_dll_directory(dll_path)
                    except Exception:
                        pass

from audio_separator.separator import Separator
from faster_whisper import WhisperModel

# =========================
# 기본값 (VRAM OOM 최적화 설정)
# =========================
MODEL_NAME = "kotoba-tech/kotoba-whisper-v2.0-faster" # 단일 고성능 모델 사용
USE_UVR = True
USE_DRC = False # DRC(acompressor) 비활성화
USE_LOUDNORM = True # 약한 loudnorm 활성화

class SimpleSegment:
    """Whisper 세그먼트 데이터의 통합 규격 클래스 (v2.0 메타데이터 지원)"""
    def __init__(self, start: float, end: float, text: str, 
                 avg_logprob: float = 0, no_speech_prob: float = 0, compression_ratio: float = 0):
        self.start = start
        self.end = end
        self.text = text.strip()
        self.avg_logprob = avg_logprob
        self.no_speech_prob = no_speech_prob
        self.compression_ratio = compression_ratio
        self.needs_review = False
        self.review_reason = []

def clear_vram():
    """VRAM 완전 해제 (Garbage Collection & Cache Clear)"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("[VRAM] GPU 메모리 정리 및 캐시 비우기 완료")

# =========================
# 유틸 및 후처리
# =========================
def format_srt_time(seconds: float) -> str:
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def clean_text(text: str) -> str:
    """비언어적 잡음 태그 제거"""
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^]]*\]', '', text)
    text = re.sub(r'[♪♬]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# =========================
# Step 0. 오디오 추출 (44.1kHz Stereo PCM)
# =========================
def extract_audio(video_path: str, output_dir: str) -> str:
    """UVR/Demucs 최적 성능을 위해 44.1kHz 스테레오로 추출"""
    print(f"[Whisper] [0] 오디오 추출 시작 (44.1kHz Stereo): {os.path.basename(video_path)}")
    out_path = os.path.join(output_dir, "raw_audio.wav")
    (
        ffmpeg
        .input(video_path)
        .output(out_path, ac=2, ar=44100, acodec='pcm_s16le')
        .run(overwrite_output=True, quiet=True)
    )
    return out_path

# =========================
# Step 1. 보컬 분리 (Demucs htdemucs_ft)
# =========================
def isolate_vocals(audio_path: str, output_dir: str) -> str:
    """합의안 v2.0: htdemucs_ft 모델 고정 사용"""
    print(f"[Whisper] [1] 보컬 분리 시도 (htdemucs_ft)")
    import time
    start = time.time()
    
    try:
        separator = Separator(output_dir=output_dir)
        # [v2.0] JAV 환경에서 검증된 htdemucs_ft 모델 사용
        separator.load_model("htdemucs_ft")
        print(f"[Whisper] [1] htdemucs_ft 실행 중...")
        output_files = separator.separate(audio_path)
    except Exception as e:
        print(f"[Whisper] [1] 보컬 분리 실패: {e}. 원본 오디오를 사용합니다.")
        return audio_path

    vocal_file = next((f for f in output_files if "Vocals" in os.path.basename(f)), output_files[0])
    if not os.path.isabs(vocal_file):
        vocal_file = os.path.join(output_dir, os.path.basename(vocal_file))
    
    print("[Whisper] [1] 보컬 분리 완료. UVR 모델 메모리 반환 중...")
    del separator
    clear_vram()
    
    print(f"[Whisper] [1] 보컬 분리 완료 (소요시간: {time.time() - start:.1f}s)")
    return vocal_file

# =========================
# Step 1.5. SNR 체크포인트 (v2.0 신규)
# =========================
def check_vocals_snr(vocals_path: str, snr_warn_threshold: float = 10.0) -> float:
    """보컬 트랙의 SNR을 측정하여 속삭임 유실 가능성 경고"""
    try:
        y, sr = librosa.load(vocals_path, sr=None)
        rms = np.sqrt(np.mean(y**2))
        # 하위 10%를 노이즈 플로어로 추정 (위원회 권장 방식)
        noise_floor = np.percentile(np.abs(y), 10)
        snr = 20 * np.log10(rms / (noise_floor + 1e-6))
        
        print(f"[Whisper] [1.5] 보컬 SNR 측정 결과: {snr:.2f}dB")
        if snr < snr_warn_threshold:
            print(f"⚠️ [WARNING] SNR이 {snr_warn_threshold}dB 미만입니다. 속삭임 대사가 소실되었을 가능성이 큽니다.")
        return snr
    except Exception as e:
        print(f"[Whisper] [1.5] SNR 측정 실패: {e}")
        return 0.0

# =========================
# Step 2. FFmpeg 복합 전처리 (위원회 합의안)
# =========================
def apply_audio_norm(audio_path: str, output_dir: str) -> str:
    """합의안 v2.0 정밀 필터 체인: 속삭임 증폭 및 대역 제한"""
    print("[Whisper] [2] 오디오 전처리 (v2.0 정밀 필터 적용)")
    out_path = os.path.join(output_dir, "preprocessed.wav")
    
    # [v2.0] 필터 파라미터 상세 설정
    # - highpass: 100Hz (저역 노이즈 제거)
    # - lowpass: 7500Hz (고역 노이즈 억제)
    # - compand: 속삭임 구간(-45dB)을 약 12dB 증폭 (-45 -> -33)
    # - loudnorm: I=-18, TP=-2, LRA=9 (과도한 정규화 방지)
    filters = (
        "highpass=f=100, "
        "lowpass=f=7500, "
        "compand=attacks=0.08:decays=0.5:points=-80/-80|-45/-33|-30/-22|0/-10:gain=3, "
        "loudnorm=I=-18:TP=-2:LRA=9"
    )
    
    (
        ffmpeg
        .input(audio_path)
        .filter_argument(filters) # 복합 필터 체인 적용
        .output(out_path, ar=16000, ac=1) # Whisper 입력을 위해 16kHz 모노 변환
        .run(overwrite_output=True, quiet=True)
    )
    return out_path

# =========================
# Step 3. Whisper 실행 (v2.0 최적 파라미터)
# =========================
def run_whisper(audio_path: str, beam_size: int = 3) -> List[SimpleSegment]:
    """합의안 v2.0: 속삭임 보존과 환각 차단의 타협점 파라미터 적용"""
    import time
    start = time.time()
    print(f"[Whisper] [3] {MODEL_NAME} 엔진 기동 (beam_size={beam_size})")
    
    model = WhisperModel(MODEL_NAME, device="cuda", compute_type="float16")
    
    # [v2.0] 전문가 위원회 권장 파라미터
    # - compression_ratio_threshold: 1.8 (반복 환각 강력 차단)
    # - log_prob_threshold: -0.9 (속삭임 보존을 위해 완화)
    # - no_speech_threshold: 0.55 (속삭임 보존)
    # - condition_on_previous_text: True (문맥 유지)
    segments, info = model.transcribe(
        audio_path, language="ja", beam_size=beam_size, best_of=3, patience=1.2,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        condition_on_previous_text=True, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=1000, speech_pad_ms=400, threshold=0.45),
        compression_ratio_threshold=1.8, log_prob_threshold=-0.9, no_speech_threshold=0.55,
        word_timestamps=True
    )
    
    result = []
    for seg in segments:
        result.append(SimpleSegment(
            seg.start, seg.end, seg.text,
            avg_logprob=seg.avg_logprob,
            no_speech_prob=seg.no_speech_prob,
            compression_ratio=seg.compression_ratio
        ))
            
    print(f"[Whisper] [3] 분석 완료 (총 {len(result)}개 구간, 소요시간: {time.time() - start:.1f}s)")
    
    del model
    clear_vram()
    return result

# =========================
# Step 4. 수치 기반 환각 필터 (v2.0)
# =========================
def filter_hallucinations(segments: List[SimpleSegment]) -> List[SimpleSegment]:
    """임계값 및 시간 밀도 기반 환각 탐지"""
    print("[Whisper] [4] 환각 필터링 및 시간 밀도 분석 중...")
    
    # 1. 정규식 필터 (메타 문구)
    meta_patterns = [
        r"ご視聴ありがとうございました", r"채널 등록", r"자막 제작", r"구독과 좋아요",
        r"お問い合わせは", r"字幕制作", r"시청해주셔서 감사합니다"
    ]
    
    # 2. 시간 밀도 이상 탐지 (30초 슬라이딩 윈도우 내 20개 초과)
    def check_density(segs):
        for i in range(len(segs)):
            window_end = segs[i].start + 30
            count = 0
            for j in range(i, len(segs)):
                if segs[j].start <= window_end:
                    count += 1
                else:
                    break
            if count > 20:
                for k in range(i, i + count):
                    segs[k].needs_review = True
                    if "High Density" not in segs[k].review_reason:
                        segs[k].review_reason.append("High Density (>20/30s)")

    check_density(segments)

    filtered = []
    for seg in segments:
        # 수치 기반 환각 판별 (v2.0 기준)
        is_hallucination = False
        
        # avg_logprob < -1.2 (기본값 -0.9에서 -0.3 여유)
        if seg.avg_logprob < -1.2:
            is_hallucination = True
            seg.review_reason.append(f"Low LogProb ({seg.avg_logprob:.2f})")
            
        # no_speech_prob > 0.7 (기본값 0.55에서 +0.15 여유)
        if seg.no_speech_prob > 0.7:
            is_hallucination = True
            seg.review_reason.append(f"High NoSpeechProb ({seg.no_speech_prob:.2f})")

        # 세그먼트 내부 반복 (4글자 이상 3회)
        if re.search(r'(.{4,})\1\1', seg.text):
            is_hallucination = True
            seg.review_reason.append("Internal Repetition")

        # 메타 패턴 매칭
        for p in meta_patterns:
            if re.search(p, seg.text):
                is_hallucination = True
                seg.review_reason.append("Meta Content Pattern")
                break

        if is_hallucination:
            seg.needs_review = True
            # 환각으로 강하게 의심되는 경우에도 일단 데이터는 유지하되 
            # 추후 AIAnalyzer에서 최종 판단하도록 flag만 설정함 (위원회 권고)
        
        filtered.append(seg)
        
    return filtered

# =========================
# Step 5. 로컬 LLM 동음이의어 교정 (Ollama)
# =========================
async def correct_with_llm(segments: List[SimpleSegment]) -> List[SimpleSegment]:
    """Ollama를 이용한 동음이의어 교정 (Qwen2.5-7B)"""
    from core.llm_engine import MultiTierRouter
    from core.app_config import LLM_TIERS
    
    # Qwen2.5-7B 로컬 티어 검색
    qwen_tier = next((t for t in LLM_TIERS if "qwen" in t["name"].lower()), None)
    if not qwen_tier:
        print("[Whisper] [5] 로컬 LLM 티어를 찾을 수 없어 교정을 스킵합니다.")
        return segments

    print(f"[Whisper] [5] 로컬 LLM 교정 시작 ({qwen_tier['name']})")
    router = MultiTierRouter(api_key="ollama")
    
    # 청분 분할 (약 10개 세그먼트 단위)
    chunk_size = 10
    chunks = [segments[i:i + chunk_size] for i in range(0, len(segments), chunk_size)]
    
    system_prompt = """너는 일본어 자막의 동음이의어 오류를 수정하는 전문가야.
오디오를 직접 듣지 못하므로 문맥을 통해서만 판단해라.
- '異常'과 '이상'의 혼동, 명백한 오자만 수정해라.
- 환각을 판별하려 하지 마라. (대사를 삭제하거나 창작 금지)
- 감탄사나 비언어음은 건드리지 마라.
- 반드시 JSON 리스트 포맷으로 [ {"index": idx, "text": "수정된 텍스트"}, ... ] 형식만 출력해라.
"""
    
    success_count = 0
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        try:
            chunk_data = [{"index": j, "text": s.text} for j, s in enumerate(chunk)]
            user_prompt = f"다음 자막 리스트의 동음이의어 오류를 수정해줘:\n{json.dumps(chunk_data, ensure_ascii=False)}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 타임아웃 180초 적용 (순차 처리)
            raw_res = await asyncio.wait_for(router.call_model(qwen_tier, messages), timeout=180.0)
            
            # JSON 파싱
            match = re.search(r'\[.*\]', raw_res, re.DOTALL)
            if match:
                corrections = json.loads(match.group(0))
                for corr in corrections:
                    idx = corr.get("index")
                    if idx is not None and idx < len(chunk):
                        chunk[idx].text = corr["text"]
                success_count += 1
        except Exception as e:
            print(f"  ⚠️ Chunk {i+1} 교정 실패: {e}")

    fail_rate = (total_chunks - success_count) / total_chunks * 100
    print(f"[Whisper] [5] LLM 교정 완료: {success_count}/{total_chunks} 청크 성공 ({fail_rate:.1f}% 실패)")
    
    return segments

# =========================
# 5. 진입점 함수 (Gatekeeper 통합)
# =========================
# =========================
# 통합 진입점 (v2.0 파이프라인 제어)
# =========================
def process_video_to_segments(video_path: str, output_dir: str, skip_vocal_sep: bool = False, with_llm: bool = True) -> List[SimpleSegment]:
    """v2.0 전문가 위원회 합의안 기반 통합 STT 공정"""
    import pysrt
    
    # [Step 1] 게이트키퍼
    base_name = os.path.splitext(video_path)[0]
    ja_srt = base_name + ".ja.srt"
    review_srt = base_name + "_review.srt"
    
    if os.path.exists(ja_srt):
        print(f"[Whisper] [0] 기존 자막 발견. 로드 중...")
        try:
            subs = pysrt.open(ja_srt, encoding='utf-8')
            return [SimpleSegment(s.start.ordinal/1000.0, s.end.ordinal/1000.0, s.text) for s in subs]
        except Exception as e:
            print(f"[Whisper] [0] 자막 로드 실패: {e}")

    os.makedirs(output_dir, exist_ok=True)
    
    # [Step 0] 오디오 추출
    raw_audio = extract_audio(video_path, output_dir)
    
    # [Step 1] 보컬 분리
    audio_path = raw_audio
    if USE_UVR and not skip_vocal_sep:
        audio_path = isolate_vocals(raw_audio, output_dir)
        
        # [Step 1.5] SNR 체크포인트
        check_vocals_snr(audio_path)
    
    # [Step 2] 경량 전처리
    preprocessed_audio = apply_audio_norm(audio_path, output_dir)
    
    # [Step 3] Whisper 실행
    segments = run_whisper(preprocessed_audio, beam_size=3)
    
    # [Step 4] 수치 기반 환각 필터
    segments = filter_hallucinations(segments)
    
    # [Step 5] 로컬 LLM 교정 (비동기 처리)
    if with_llm:
        try:
            segments = asyncio.run(correct_with_llm(segments))
        except Exception as e:
            print(f"[Whisper] [5] LLM 교정 단계 치명적 오류: {e}")
    
    # [Step 6] 결과 저장
    save_srt(segments, ja_srt, review_srt=review_srt)
    
    return segments

def save_srt(segments: List[SimpleSegment], srt_path: str, review_srt: str = None) -> None:
    """[Step 6] 메인 및 검토용 SRT 저장"""
    import pysrt
    subs_main = pysrt.SubRipFile()
    subs_review = pysrt.SubRipFile()
    
    idx_main = 1
    idx_review = 1
    
    for seg in segments:
        text = clean_text(seg.text)
        if not text: continue
        
        # [v2.0] 검토 마커 추가
        main_text = text
        if seg.needs_review:
            main_text = f"[⚠ REVIEW] {text}"
        
        # 타이밍 변환 유틸
        def set_time(item_time, total_ms):
            item_time.milliseconds = total_ms % 1000
            s = total_ms // 1000
            item_time.seconds = s % 60
            m = s // 60
            item_time.minutes = m % 60
            item_time.hours = m // 60

        # 메인 아이템 생성
        item = pysrt.SubRipItem(index=idx_main, text=main_text)
        set_time(item.start, int(seg.start * 1000))
        set_time(item.end, int(seg.end * 1000))
        subs_main.append(item)
        idx_main += 1
        
        # 검토용 아이템 생성
        if seg.needs_review:
            reason = ", ".join(seg.review_reason)
            rev_text = f"[{reason}]\n{text}"
            rev_item = pysrt.SubRipItem(index=idx_review, text=rev_text)
            set_time(rev_item.start, int(seg.start * 1000))
            set_time(rev_item.end, int(seg.end * 1000))
            subs_review.append(rev_item)
            idx_review += 1
        
    subs_main.save(srt_path, encoding='utf-8')
    if idx_review > 1 and review_srt:
        subs_review.save(review_srt, encoding='utf-8')
        print(f"[Whisper] [6] 검토용 자막 저장 완료: {os.path.basename(review_srt)}")
    
    print(f"[Whisper] [6] 메인 자막 저장 완료: {os.path.basename(srt_path)}")

if __name__ == "__main__":
    pass