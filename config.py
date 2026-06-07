"""全局配置"""
from pathlib import Path

OUTPUT_DIR = Path("output")
CLIPS_DIR = OUTPUT_DIR / "clips"
FRAMES_DIR = OUTPUT_DIR / "frames"
DATA_DIR = OUTPUT_DIR / "data"

# FFmpeg 路径
FFMPEG_PATH = "G:/ai_webui/video_create/ffmpeg/ffmpeg-2024-07-10-git-1a86a7a48d-full_build/ffmpeg-2024-07-10-git-1a86a7a48d-full_build/bin/ffmpeg.exe"

HOP_LENGTH = 512
FRAME_LENGTH = 2048
SCENE_THRESHOLD = 30.0

ENERGY_WEIGHT = 0.4
MOTION_WEIGHT = 0.3
VISUAL_IMPACT_WEIGHT = 0.3

FFMPEG_CRF = 23
FFMPEG_PRESET = "medium"
MAX_CONTINUOUS_CHARACTER = 4.0
