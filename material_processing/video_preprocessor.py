"""
Video preprocessor - auto-transcode incompatible formats (HEVC, MKV, FLAC, etc.)
to H.264 + AAC MP4 that OpenCV can read for scene detection.
"""
import subprocess, tempfile, shutil
from pathlib import Path

FFMPEG_PATH = r"G:\ai_webui\video_create\ffmpeg\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\bin\ffmpeg.exe"


def _has_non_ascii(path: str) -> bool:
    try:
        path.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def ensure_compatible(video_path: str, work_dir: str = None) -> str:
    """Check if video is OpenCV-compatible, transcode if needed.
    Returns path to a compatible video file."""
    path = Path(video_path)

    # Quick check: try to open with OpenCV
    if _is_opencv_compatible(str(path)):
        print(f"  Video format compatible: {path.name}", flush=True)
        return str(path)

    # Need to transcode
    print(f"  Transcoding {path.name} to H.264 MP4...", flush=True)
    return _transcode(str(path), work_dir)


def _is_opencv_compatible(video_path: str) -> bool:
    """Test if OpenCV can open this video"""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap is None or not cap.isOpened():
            return False
        ret, frame = cap.read()
        cap.release()
        return ret and frame is not None and frame.shape[0] > 0
    except Exception:
        return False


def _transcode(video_path: str, work_dir: str = None) -> str:
    """Transcode video to H.264 + AAC MP4 using FFmpeg"""
    src = Path(video_path)

    # Handle Unicode paths
    input_path = str(src.resolve())
    cleanup_src = None
    if _has_non_ascii(input_path):
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_copy = tmp_dir / ("input" + src.suffix)
        shutil.copy2(src, tmp_copy)
        input_path = str(tmp_copy)
        cleanup_src = tmp_dir

    # Output path
    if work_dir:
        out = Path(work_dir) / f"{src.stem}_compatible.mp4"
    else:
        out = Path(tempfile.mktemp(suffix=".mp4"))

    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            FFMPEG_PATH, "-y", "-i", input_path,
            "-c:v", "libx264", "-crf", "23",
            "-preset", "fast",
            "-c:a", "aac", "-ar", "44100",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=3600)

        if result.returncode != 0 or not out.exists():
            raise RuntimeError(
                f"Transcode failed: {result.stderr.decode('utf-8', errors='replace')[-300:]}")

        print(f"  Transcoded to: {out.name} ({out.stat().st_size / 1024 / 1024:.0f}MB)", flush=True)
        return str(out)

    finally:
        if cleanup_src:
            for f in cleanup_src.iterdir():
                f.unlink(missing_ok=True)
            cleanup_src.rmdir()
