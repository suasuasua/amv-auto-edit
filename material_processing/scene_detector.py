"""Scene detection module - using PySceneDetect Python API"""
import json
from pathlib import Path

class SceneDetector:
    def __init__(self, threshold=30.0):
        self.threshold = threshold

    def detect_scenes(self, video_path: str, output_dir: str = None) -> list:
        """Detect scenes and return timestamp list"""
        try:
            from scenedetect import detect, ContentDetector, AdaptiveDetector
            from scenedetect.frame_timecode import FrameTimecode
        except ImportError:
            raise RuntimeError("PySceneDetect not installed. Run: pip install scenedetect")

        scenes = detect(video_path, ContentDetector(threshold=self.threshold))
        
        result = []
        for i, (start, end) in enumerate(scenes):
            result.append({
                "start": start.get_seconds(),
                "end": end.get_seconds(),
                "duration": end.get_seconds() - start.get_seconds()
            })
        
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / "scenes.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return result
