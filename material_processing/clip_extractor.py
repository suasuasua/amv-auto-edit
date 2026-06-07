"""?????? - ?????????????"""
import subprocess
import json
from pathlib import Path

class ClipExtractor:
    def __init__(self, ffmpeg_path=None):
        if ffmpeg_path is None:
            from config import FFMPEG_PATH
            ffmpeg_path = FFMPEG_PATH
        self.ffmpeg_path = ffmpeg_path

    def extract_clips(self, video_path: str, scenes: list, output_dir: str) -> list:
        """????????????? clip ??????"""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        clip_list = []
        for i, scene in enumerate(scenes):
            output_path = out_dir / f"clip{i + 1:04d}.mp4"
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-ss", str(scene["start"]),
                "-to", str(scene["end"]),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-y",
                str(output_path)
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=300)
            
            if output_path.exists():
                clip_list.append({
                    "clip_id": f"{i + 1:04d}",
                    "file": str(output_path),
                    "start": scene["start"],
                    "end": scene["end"],
                    "duration": scene["end"] - scene["start"]
                })
        
        return clip_list

    def save_clip_manifest(self, clips: list, output_path: str):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(clips, ensure_ascii=False, indent=2), encoding="utf-8")
