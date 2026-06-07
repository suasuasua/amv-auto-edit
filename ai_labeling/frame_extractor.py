"""Key frame extraction module"""
import subprocess
from pathlib import Path

class FrameExtractor:
    def __init__(self, ffmpeg_path=None):
        if ffmpeg_path is None:
            from config import FFMPEG_PATH
            ffmpeg_path = FFMPEG_PATH
        self.ffmpeg_path = ffmpeg_path

    def extract_middle_frame(self, video_path: str, output_path: str, duration: float):
        """Extract middle frame from video"""
        mid_time = duration / 2
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-ss", str(mid_time),
            "-vframes", "1",
            "-q:v", "2",
            "-y", str(out)
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return str(out) if out.exists() else None

    def extract_key_frames(self, video_path: str, output_dir: str, clip_id: str, duration: float, num_frames: int = 3):
        """Extract evenly spaced frames from video clip"""
        out_dir = Path(output_dir) / clip_id
        out_dir.mkdir(parents=True, exist_ok=True)
        
        frames = []
        for i in range(num_frames):
            ts = duration * (i + 1) / (num_frames + 1)
            out_path = out_dir / f"frame_{i+1:02d}.jpg"
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-ss", str(ts),
                "-vframes", "1",
                "-q:v", "2",
                "-y", str(out_path)
            ]
            subprocess.run(cmd, capture_output=True, timeout=30)
            if out_path.exists():
                frames.append(str(out_path))
        
        return frames
