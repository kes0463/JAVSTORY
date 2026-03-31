import os
import json
from faster_whisper import WhisperModel

class AudioProcessor:
    def __init__(self, config_path="config.json"):
        self.load_config(config_path)
        
        print("[Audio] Whisper Model 로딩 중... (Large-v2 on CUDA)")
        # WhisperJav 기본 엔진 세팅 (Large V2, float16)
        self.model = WhisperModel(
            self.model_settings.get("model_size_or_path", "large-v2"),
            device=self.model_settings.get("device", "cuda"),
            compute_type=self.model_settings.get("compute_type", "float16")
        )

    def load_config(self, config_path):
        """config.json 에서 사용자 요청 파라미터(WhisperJav PASS 2) 로딩"""
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            
        self.model_settings = cfg.get("Model_Settings", {})
        self.decoding_settings = cfg.get("Decoding_Settings", {})
        self.quality_settings = cfg.get("Quality_Thresholds_and_Advanced", {})
        
        # VAD 매개변수 조립
        vad_cfg = cfg.get("VAD_Settings", {})
        self.use_vad = vad_cfg.get("vad_filter", True)
        self.vad_params = dict(
            threshold=vad_cfg.get("vad_threshold", 0.02),
            min_speech_duration_ms=vad_cfg.get("vad_min_speech_duration_ms", 100),
            min_silence_duration_ms=vad_cfg.get("vad_min_silence_duration_ms", 300),
            max_speech_duration_s=vad_cfg.get("vad_max_speech_duration_s", 11),
            speech_pad_ms=vad_cfg.get("vad_speech_pad_ms", 400)
        )

    def extract_and_transcribe(self, audio_source_path):
        """
        영상(또는 음원) 경로를 받아 VAD + 고급 필터를 먹여 번역용 기초 텍스트(타임스탬프) 추출
        """
        print(f"[Audio] 음성 텍스트 추출 시작: {os.path.basename(audio_source_path)}")
        
        # faster-whisper는 자동으로 내부적으로 FFmpeg을 통해 오디오 트랙을 무변환 추출하여 돌림
        segments, info = self.model.transcribe(
            audio_source_path,
            language="ja",  # JAV 기본 언어 강제 지정
            beam_size=self.decoding_settings.get("beam_size", 8),
            best_of=self.decoding_settings.get("best_of", 8),
            patience=self.decoding_settings.get("patience", 2.0),
            temperature=self.decoding_settings.get("temperature", 0.0),
            word_timestamps=self.decoding_settings.get("word_timestamps", True),
            
            # 할루시네이션(무반복 헛소리) 제어 임계값
            condition_on_previous_text=self.quality_settings.get("condition_on_previous_text", False),
            logprob_threshold=self.quality_settings.get("logprob_threshold", -1.2),
            no_speech_threshold=self.quality_settings.get("no_speech_threshold", 0.4),
            repetition_penalty=self.quality_settings.get("repetition_penalty", 1.5),
            no_repeat_ngram_size=self.quality_settings.get("no_repeat_ngram_size", 2),
            initial_prompt=self.quality_settings.get("initial_prompt", ""),
            
            # Silero VAD (단어별 미세 정적 필터링)
            vad_filter=self.use_vad,
            vad_parameters=self.vad_params
        )
        
        print(f"[Audio] 오디오 언어 감지: {info.language} (정확도: {info.language_probability})")
        
        results = []
        for segment in segments:
            # 텍스트가 있는 구간만 저장
            text = segment.text.strip()
            if text:
                results.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": text
                })
                
        return results
