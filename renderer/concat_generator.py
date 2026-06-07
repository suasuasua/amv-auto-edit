from pathlib import Path
import subprocess

FFMPEG_PATH = r"G:\ai_webui\video_create\ffmpeg\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\bin\ffmpeg.exe"

class ConcatGenerator:
    def generate(self, timeline, output_path):
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for i, entry in enumerate(timeline):
            src = Path(entry["file"])
            start = entry["start"]
            dur = entry["end"] - start
            if dur <= 0:
                continue
            trimmed = out.parent / f"_t_{i:04d}.mp4"
            cmd = [
                FFMPEG_PATH, "-y",
                "-i", str(src.resolve()),
                "-ss", str(entry.get("clip_offset", 0)),
                "-t", str(dur),
                "-c:v", "libx264", "-crf", "23",
                "-preset", "fast",
                "-an",  # no audio (music will be overlaid)
                "-pix_fmt", "yuv420p",
                str(trimmed)
            ]
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
            if trimmed.exists() and trimmed.stat().st_size > 0:
                lines.append("file '" + str(trimmed.resolve()) + "'")
        out.write_text("\n".join(lines), encoding="utf-8")
        return str(out)
