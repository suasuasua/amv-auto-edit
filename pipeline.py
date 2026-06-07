"""AMV Auto-edit Pipeline"""
import sys, json
from pathlib import Path
from config import OUTPUT_DIR, CLIPS_DIR, FRAMES_DIR, DATA_DIR

from music_analysis.beat_analyzer import BeatAnalyzer
from music_analysis.structure_analyzer import StructureAnalyzer
from material_processing.video_preprocessor import ensure_compatible
from material_processing.scene_detector import SceneDetector
from material_processing.clip_extractor import ClipExtractor
from ai_labeling.clip_analyzer import ClipAnalyzer
from timeline_planner.planner import TimelinePlanner
from renderer.concat_generator import ConcatGenerator
from renderer.ffmpeg_renderer import FFmpegRenderer


class AMVPipeline:
    def __init__(self, api_key: str = None, use_vlm: bool = True, max_clips: int = 60):
        self.max_clips = max_clips
        self.beat_analyzer = BeatAnalyzer()
        self.structure_analyzer = StructureAnalyzer()
        self.scene_detector = SceneDetector()
        self.clip_extractor = ClipExtractor()
        self.clip_analyzer = ClipAnalyzer(api_key=api_key, use_local_vlm=use_vlm,
                                          vlm_model="Qwen/Qwen2-VL-2B-Instruct")
        self.planner = TimelinePlanner()
        self.concat_gen = ConcatGenerator()
        self.renderer = FFmpegRenderer()

        for d in [CLIPS_DIR, FRAMES_DIR, DATA_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def run(self, music_path: str, video_path: str, output_path: str = None):
        """Run full AMV pipeline with auto-transcoding"""
        print("=" * 50)
        print("AMV Auto-edit Pipeline")
        print("=" * 50)

        # Step 0: Video compatibility check
        print("\n[0/5] Checking video format...")
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        video = ensure_compatible(video_path, work_dir=str(OUTPUT_DIR))
        print(f"    Using: {Path(video).name}")

        # Step 1: Music Analysis
        print("\n[1/5] Analyzing music beat...")
        beats_data = self.beat_analyzer.analyze(music_path)
        self.beat_analyzer.save(beats_data, str(DATA_DIR / "music_beats.json"))
        print(f"    BPM: {beats_data['bpm']}, Beats: {len(beats_data['beats'])}, "
              f"Duration: {beats_data['duration']:.0f}s")

        print("\n[1/5] Analyzing song structure...")
        structure = self.structure_analyzer.analyze(music_path, beats_data["beats"])
        self.structure_analyzer.save(structure, str(DATA_DIR / "music_structure.json"))
        types = [s["type"] for s in structure]
        print(f"    Sections: {', '.join(types)} ({len(structure)} segments)")

        # Clip budget: limit to max_clips for long videos
        total_beats = len(beats_data["beats"])
        clip_budget = min(total_beats, self.max_clips)
        print(f"    Clip budget: {clip_budget} (max={self.max_clips})")

        # Step 2: Video Processing
        print("\n[2/5] Detecting scenes...")
        scenes = self.scene_detector.detect_scenes(video, str(CLIPS_DIR))
        print(f"    Found {len(scenes)} scenes")

        # Sample to clip budget
        if len(scenes) > clip_budget:
            scenes = sorted(scenes, key=lambda s: s["end"] - s["start"], reverse=True)
            scenes = sorted(scenes[:clip_budget], key=lambda s: s["start"])
            print(f"    Sampled to {len(scenes)} longest scenes for variety")

        if not scenes:
            print("    Warning: no scene changes detected, using full video as single clip")
            scenes = [{"start": 0.0, "end": beats_data["duration"], "duration": beats_data["duration"]}]

        print("\n[2/5] Extracting clips...")
        clips = self.clip_extractor.extract_clips(video, scenes, str(CLIPS_DIR))
        # Filter out 0-byte clips
        clips = [c for c in clips if Path(c["file"]).stat().st_size > 0]
        self.clip_extractor.save_clip_manifest(clips, str(DATA_DIR / "clip_manifest.json"))
        print(f"    Extracted {len(clips)} valid clips")

        # Step 3: AI Labeling
        print("\n[3/5] Extracting frames...")
        from ai_labeling.frame_extractor import FrameExtractor
        fe = FrameExtractor()
        for i, clip in enumerate(clips):
            fe.extract_middle_frame(clip["file"], str(FRAMES_DIR / f"{clip['clip_id']}_mid.jpg"), clip["duration"])
            if (i + 1) % 10 == 0 or i == len(clips) - 1:
                print(f"    Frames: {i+1}/{len(clips)}", flush=True)

        print("\n[3/5] Labeling clips...")
        labeled = self.clip_analyzer.batch_analyze(clips, str(FRAMES_DIR))
        self.clip_analyzer.save(labeled, str(DATA_DIR / "clip_metadata.json"))
        print(f"    Labeled {len(labeled)} clips")

        # Step 4: Timeline Planning
        print("\n[4/5] Planning timeline...")
        timeline = self.planner.plan(beats_data, structure, labeled)
        self.planner.save(timeline, str(DATA_DIR / "timeline.json"))
        print(f"    Generated {len(timeline)} timeline entries")

        # Step 5: Render
        print("\n[5/5] Rendering video with music track...")
        concat_file = self.concat_gen.generate(timeline, str(OUTPUT_DIR / "concat.txt"))
        if output_path is None:
            output_path = str(OUTPUT_DIR / "amv_output.mp4")
        final_path = self.renderer.render_concat(concat_file, output_path, music_path=music_path)
        print(f"    Output: {final_path}")

        print("\n" + "=" * 50)
        print("AMV Complete!")
        print("=" * 50)
        return final_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AMV Auto-edit Tool - music beat sync video editor")
    parser.add_argument("music", help="Music file path (MP3, M4A, WAV, FLAC, etc.)")
    parser.add_argument("video", help="Anime/video file path (auto-transcodes HEVC/MKV)")
    parser.add_argument("--max-clips", type=int, default=60,
                        help="Max clips to analyze (default: 60)")
    parser.add_argument("-o", "--output", help="Output video path", default=None)
    parser.add_argument("--no-vlm", action="store_true", help="Disable local VLM labeling (use mock)")
    args = parser.parse_args()
    pipeline = AMVPipeline(use_vlm=not args.no_vlm, max_clips=args.max_clips)
    pipeline.run(args.music, args.video, args.output)


if __name__ == "__main__":
    main()
