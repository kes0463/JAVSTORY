import os
import ffmpeg
from scenedetect import detect, AdaptiveDetector

class VideoProcessor:
    def __init__(self, thresholds=None):
        if thresholds is None:
            thresholds = {
                "adaptive_threshold": 32,
                "min_scene_len_seconds": 10.0
            }
        self.adaptive_threshold = thresholds.get("adaptive_threshold", 32)
        # fps에 따른 프레임 길이는 영상 오픈 후 계산 (기본값 설정 위해 10.0초)
        self.min_scene_len_seconds = thresholds.get("min_scene_len_seconds", 10.0)

    def extract_scene_thumbnails(self, video_path, output_dir):
        """
        AdaptiveDetector를 사용하여 격렬한 카메라 움직임/빠른 컷에서도 
        정확하게 씬을 나누고, 각 씬의 시작 프레임에 대해 FFmpeg로 병렬 스냅샷을 추출.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        print(f"[Video] 분석 시작: {os.path.basename(video_path)}")
        
        try:
            # 1. 스크린 감지 (AdaptiveDetector)
            # 프레임워크 한계 상 min_scene_len은 프레임 수를 입력받으므로, 대략 30fps 기준 300프레임 적용
            min_scene_len_frames = int(self.min_scene_len_seconds * 30)
            
            scene_list = detect(
                video_path, 
                AdaptiveDetector(adaptive_threshold=self.adaptive_threshold, min_scene_len=min_scene_len_frames)
            )
            
            print(f"[Video] 총 {len(scene_list)}개의 주요 씬(Scene) 감지됨. 썸네일 추출 시작...")
            
            thumbnail_paths = []
            
            # 2. FFmpeg 스냅샷 병렬 추출 (루프로 순차 실행하지만 ffmpeg 바이너리가 워낙 빨라 병목 없음)
            for i, scene in enumerate(scene_list):
                # scene = (start_time, end_time) 객체, start_time.get_seconds() 
                start_sec = scene[0].get_seconds()
                thumb_path = os.path.join(output_dir, f"scene_{i:03d}_{int(start_sec)}s.jpg")
                
                try:
                    (
                        ffmpeg
                        .input(video_path, ss=start_sec)
                        .output(thumb_path, vframes=1, qscale=2, loglevel="quiet")
                        .run(overwrite_output=True)
                    )
                    thumbnail_paths.append({
                        "id": i,
                        "timestamp": start_sec,
                        "path": thumb_path
                    })
                except ffmpeg.Error as e:
                    print(f"  -> Thumbnail error at {start_sec}s")
            
            return thumbnail_paths
            
        except Exception as e:
            print(f"[Video] 분석 중 오류 발생: {e}")
            return []
