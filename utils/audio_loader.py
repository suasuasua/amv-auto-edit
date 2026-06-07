"""Audio loading utility - supports all formats via FFmpeg fallback, handles Unicode paths"""
import subprocess, tempfile, shutil
from pathlib import Path

FFMPEG_PATH = r"G:\ai_webui\video_create\ffmpeg\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\ffmpeg-2024-07-10-git-1a86a7a48d-full_build\bin\ffmpeg.exe"


def _has_non_ascii(path: str) -> bool:
    try:
        path.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def load_audio(audio_path: str, target_sr: int = 22050) -> tuple:
    """Load audio from any format (M4A, MP3, FLAC, WAV, etc.), normalize to mono + target_sr"""
    import soundfile as sf
    from scipy.signal import resample

    path = Path(audio_path)

    # Try direct soundfile read first
    try:
        y, sr = sf.read(str(path))
        return _normalize(y, sr, target_sr)
    except Exception:
        pass

    # FFmpeg fallback
    # Use binary subprocess mode to avoid GBK decode issues on Windows
    input_path = str(path.resolve())

    # Copy to ASCII-only temp path if needed (Windows FFmpeg Unicode bug)
    cleanup_path = None
    if _has_non_ascii(input_path):
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_copy = tmp_dir / "input_audio.m4a"
        shutil.copy2(path, tmp_copy)
        input_path = str(tmp_copy)
        cleanup_path = tmp_dir

    tmp_wav = Path(tempfile.mktemp(suffix=".wav"))

    try:
        cmd = [FFMPEG_PATH, "-y", "-i", input_path,
               "-ac", "1", "-ar", str(target_sr),
               "-f", "wav", "-bitexact", str(tmp_wav)]
        subprocess.run(cmd, capture_output=True, timeout=300, check=True)
        y, sr = sf.read(str(tmp_wav))
        return _normalize(y, sr, target_sr)
    finally:
        tmp_wav.unlink(missing_ok=True)
        if cleanup_path and cleanup_path.exists():
            for f in cleanup_path.iterdir():
                f.unlink(missing_ok=True)
            cleanup_path.rmdir()


def _normalize(y, sr, target_sr):
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != target_sr and sr > 0:
        from scipy.signal import resample
        y = resample(y, int(len(y) * target_sr / sr))
    return y.astype(float), target_sr
