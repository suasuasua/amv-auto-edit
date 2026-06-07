"""FFmpeg renderer - concat video + overlay music audio"""
import subprocess
from pathlib import Path

FFMPEG_PATH = r"G:\ai_webui\video_create\ffmpeg\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\bin\ffmpeg.exe"


class FFmpegRenderer:
    def __init__(self, ffmpeg_path=None, crf=23, preset="medium"):
        if ffmpeg_path is None:
            ffmpeg_path = FFMPEG_PATH
        self.ffmpeg_path = ffmpeg_path
        self.crf = crf
        self.preset = preset

    def render_concat(self, concat_file: str, output_path: str, music_path: str = None) -> str:
        """Render video from concat file, with optional music overlay.
        
        If music_path is provided:
          1. Concat all trimmed clips (no audio) to temp video
          2. Add music as audio track, trimmed to match video duration
        Otherwise: simple concat with -c copy
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if music_path is None:
            # Simple concat copy
            cmd = [self.ffmpeg_path, "-f", "concat", "-safe", "0",
                   "-i", concat_file, "-c", "copy", "-y", str(out)]
            subprocess.run(cmd, capture_output=True, text=True, timeout=3600, check=True)
            return str(out)

        # With music: concat video only, then add music audio
        # Step 1: check music duration
        dur_cmd = [self.ffmpeg_path, "-i", music_path]
        dur_r = subprocess.run(dur_cmd, capture_output=True, timeout=30)
        stderr_text = dur_r.stderr.decode("utf-8", errors="replace")
        import re
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", stderr_text)
        if m:
            music_dur = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
        else:
            music_dur = 180  # fallback

        # Step 2: concat video only (no audio), get video duration via first pass
        # First do a quick concat of just file list to get total duration
        # Then concat with -an and add music audio

        # Concat video with -an (no audio), then mux music on top
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-i", music_path,
            "-filter_complex",
            "[0:v]format=yuv420p[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264", "-crf", str(self.crf), "-preset", self.preset,
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(out)
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=7200)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"Render failed: {err}")

        return str(out)

    def add_beat_effects(self, input_path: str, output_path: str, timeline: list):
        """V3: add beat-synced visual effects"""
        pass
