from dataclasses import dataclass, field

@dataclass
class PipelineConfig:
    # Step 1: Text Skeleton
    density_window_sec: float = 30.0
    density_step_sec: float = 15.0
    talk_threshold: float = 6.0
    sparse_threshold: float = 1.5
    min_zone_duration: float = 60.0
    color_change_threshold: float = 55.0
    
    # Step 2: Signal Analysis
    optical_flow_fps: float = 2.0
    cut_exclusion_sec: float = 2.0
    dip_ratio: float = 0.35
    min_dip_sec: float = 2.0
    max_dip_sec: float = 15.0
    fusion_tolerance_sec: float = 15.0
    
    # Step 3: VLM Strike
    vlm_max_calls: int = 25
    vlm_min_interval_sec: float = 45.0
    vlm_min_confidence: float = 0.45
    vlm_model: str = "gpt-4o"
    vlm_circuit_breaker_limit: int = 3  # 연속 실패 허용치

# Global Instance
cfg = PipelineConfig()
