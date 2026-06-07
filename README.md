# AMV Auto-Edit Pipeline

> 基于音乐节奏的动漫混剪视频自动生成工具

## 功能

- 音乐节拍分析（BPM、鼓点检测、乐曲结构）
- 视频场景检测与自动裁剪
- 视觉语言模型（VLM）自动标注镜头内容
- 基于鼓点对齐的时间线规划
- 自动渲染输出，叠入音乐音频

## 系统要求

- Python 3.10+
- FFmpeg（含 libx264、aac 编码器）
- （可选）NVIDIA GPU + CUDA，用于 VLM 标注

## 安装

```bash
# 基础依赖
pip install librosa numpy scipy soundfile scenedetect pillow

# VLM 标注（可选，使用 ComfyUI 的 Python 环境）
# 参考: P:\ComfyUI_windows_portable\python_embeded\python.exe
# 需要安装 torch, transformers, qwen-vl-utils
```

## 使用

```bash
python pipeline.py <音乐文件> <视频文件> [-o 输出路径] [--max-clips 60] [--no-vlm]
```

### 示例

```bash
python pipeline.py song.mp4 anime.mkv -o output.mp4
python pipeline.py song.m4a anime.mkv --max-clips 80 --no-vlm
```

## 项目结构

```
├── pipeline.py                  # 主管线入口
├── config.py                    # 全局配置
├── music_analysis/              # 音乐分析
│   ├── beat_analyzer.py         # 节拍 + 鼓点检测
│   └── structure_analyzer.py    # 乐曲结构分析 (intro/verse/chorus/drop/outro)
├── material_processing/         # 视频处理
│   ├── video_preprocessor.py    # 视频格式兼容转换
│   ├── scene_detector.py        # 场景检测
│   └── clip_extractor.py        # 镜头裁剪
├── ai_labeling/                 # 镜头标注
│   ├── clip_analyzer.py         # 标注调度器
│   ├── local_vlm.py             # Qwen2-VL 本地模型分析
│   └── frame_extractor.py       # 关键帧提取
├── timeline_planner/            # 时间线规划
│   ├── planner.py               # 时间线生成器
│   └── rules.py                 # 匹配规则 + 剪切策略
├── renderer/                    # 渲染
│   ├── concat_generator.py      # 裁剪片段生成
│   └── ffmpeg_renderer.py       # FFmpeg 合成 + 音乐叠加
└── utils/
    ├── audio_loader.py          # 音频加载（支持 Unicode 路径）
    └── file_utils.py            # 文件工具
```

## 工作流程

1. 分析音乐节拍（BPM、鼓点得分、强拍位置）
2. 分析乐曲结构（识别段落类型）
3. 检测视频场景变化，裁剪镜头片段
4. （可选）VLM 自动标注每个镜头的内容和能量
5. 根据规则规划时间线：镜头匹配段落 + 鼓点对齐切换
6. FFmpeg 渲染输出，音乐音频覆盖

## 配置

编辑 `config.py`：
- `FFMPEG_PATH`：FFmpeg 可执行文件路径
- `SCENE_THRESHOLD`：场景检测灵敏度
- `ENERGY_WEIGHT` / `MOTION_WEIGHT` / `VISUAL_IMPACT_WEIGHT`：评分权重
