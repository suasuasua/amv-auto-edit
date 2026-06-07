#!/usr/bin/env python3
"""AMV Auto-Edit Web UI - Gradio interface"""
import os, sys, json, threading, time, tempfile, shutil
from pathlib import Path
from datetime import datetime
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATUS_FILE = None
STATUS_LOCK = threading.Lock()
CANCEL_FLAG = threading.Event()


def _status(key, value):
    if STATUS_FILE is None: return
    with STATUS_LOCK:
        data = {}
        if STATUS_FILE.exists():
            try: data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            except: pass
        data[key] = value
        data["_updated"] = time.time()
        STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_status():
    if STATUS_FILE is None or not STATUS_FILE.exists():
        return {"step": "idle", "progress": 0, "log": ""}
    try: return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except: return {"step": "idle", "progress": 0, "log": ""}


def run_pipeline(music_path, video_path, max_clips, drum_threshold, cut_frequency, use_vlm):
    global CANCEL_FLAG
    CANCEL_FLAG.clear()
    output_dir = Path(tempfile.mkdtemp(prefix="amv_output_"))
    _status("step", "init"); _status("progress", 0); _status("log", ""); _status("output", None)
    log_lines = []
    for d in [output_dir / "clips", output_dir / "frames", output_dir / "data"]:
        d.mkdir(parents=True, exist_ok=True)

    try:
        log_lines.append("[0/6] Checking input files...")
        _status("log", "\n".join(log_lines[-50:]))
        if not Path(music_path).exists(): raise FileNotFoundError(f"Music: {music_path}")
        if not Path(video_path).exists(): raise FileNotFoundError(f"Video: {video_path}")
        log_lines.append(f"    Music: {Path(music_path).name}")
        log_lines.append(f"    Video: {Path(video_path).name}")
        _status("progress", 5)
        if CANCEL_FLAG.is_set(): return

        from music_analysis.beat_analyzer import BeatAnalyzer
        from music_analysis.structure_analyzer import StructureAnalyzer
        from material_processing.video_preprocessor import ensure_compatible
        from material_processing.scene_detector import SceneDetector
        from material_processing.clip_extractor import ClipExtractor
        from ai_labeling.clip_analyzer import ClipAnalyzer
        from ai_labeling.frame_extractor import FrameExtractor
        from timeline_planner.planner import TimelinePlanner
        from renderer.concat_generator import ConcatGenerator
        from renderer.ffmpeg_renderer import FFmpegRenderer

        # Step 1: Music
        log_lines.append("\n[1/6] Analyzing music...")
        _status("log", "\n".join(log_lines[-50:])); _status("step", "music")
        ba = BeatAnalyzer(); beats = ba.analyze(music_path)
        ba.save(beats, str(output_dir / "data/music_beats.json"))
        log_lines.append(f"    BPM: {beats['bpm']}, {len(beats['beats'])} beats")
        _status("progress", 15)
        if CANCEL_FLAG.is_set(): return

        sa = StructureAnalyzer(); struct = sa.analyze(music_path, beats["beats"])
        sa.save(struct, str(output_dir / "data/music_structure.json"))
        from collections import Counter
        for t, c in Counter(s["type"] for s in struct).items(): log_lines.append(f"    {t}: {c}")
        _status("progress", 25)
        if CANCEL_FLAG.is_set(): return

        # Step 2: Video
        log_lines.append("\n[2/6] Processing video...")
        _status("log", "\n".join(log_lines[-50:])); _status("step", "video")
        video = ensure_compatible(video_path, work_dir=str(output_dir))
        sd = SceneDetector(); scenes = sd.detect_scenes(video, str(output_dir / "clips"))
        log_lines.append(f"    {len(scenes)} scenes")
        clip_budget = min(len(beats["beats"]), max_clips)
        if len(scenes) > clip_budget:
            scenes = sorted(scenes, key=lambda s: s["end"]-s["start"], reverse=True)[:clip_budget]
            log_lines.append(f"    Sampled to {clip_budget}")
        if not scenes:
            scenes = [{"start": 0.0, "end": beats["duration"], "duration": beats["duration"]}]
        ce = ClipExtractor(); clips = ce.extract_clips(video, scenes, str(output_dir / "clips"))
        clips = [c for c in clips if Path(c["file"]).stat().st_size > 0]
        ce.save_clip_manifest(clips, str(output_dir / "data/clip_manifest.json"))
        log_lines.append(f"    {len(clips)} clips")
        _status("progress", 50)
        if CANCEL_FLAG.is_set(): return

        # Step 3: Frames + Labeling
        log_lines.append("\n[3/6] Extracting frames..." if not use_vlm else "\n[3/6] Extracting frames + VLM...")
        _status("log", "\n".join(log_lines[-50:])); _status("step", "labeling")
        fe = FrameExtractor()
        for i, clip in enumerate(clips):
            fe.extract_middle_frame(clip["file"], str(output_dir/"frames"/f"{clip['clip_id']}_mid.jpg"), clip["duration"])
            if (i+1) % 15 == 0:
                log_lines.append(f"    {i+1}/{len(clips)}"); _status("log", "\n".join(log_lines[-50:]))
        log_lines.append(f"    Frames: {len(clips)}")
        ca = ClipAnalyzer(use_local_vlm=use_vlm, vlm_model="Qwen/Qwen2-VL-2B-Instruct")
        labeled = ca.batch_analyze(clips, str(output_dir / "frames"))
        ca.save(labeled, str(output_dir / "data/clip_metadata.json"))
        log_lines.append(f"    Labeled {len(labeled)} clips")
        _status("progress", 75)
        if CANCEL_FLAG.is_set(): return

        # Step 4: Timeline
        log_lines.append("\n[4/6] Planning timeline...")
        _status("log", "\n".join(log_lines[-50:])); _status("step", "timeline")
        planner = TimelinePlanner(); timeline = planner.plan(beats, struct, labeled)
        planner.save(timeline, str(output_dir / "data/timeline.json"))
        total_dur = sum(e["duration"] for e in timeline)
        avg_dur = total_dur / len(timeline) if timeline else 0
        log_lines.append(f"    {len(timeline)} entries, avg {avg_dur:.1f}s")
        _status("progress", 85)
        if CANCEL_FLAG.is_set(): return

        # Step 5: Render
        log_lines.append("\n[5/6] Rendering...")
        _status("log", "\n".join(log_lines[-50:])); _status("step", "render")
        cg = ConcatGenerator(); concat_file = cg.generate(timeline, str(output_dir/"concat.txt"))
        renderer = FFmpegRenderer()
        final = renderer.render_concat(concat_file, str(output_dir/"amv_output.mp4"), music_path=music_path)
        size_mb = Path(final).stat().st_size / 1024 / 1024
        log_lines.append(f"    Done ({size_mb:.1f} MB)")
        _status("progress", 100); _status("step", "done"); _status("output", final)

        project_out = Path(sys.path[0])/"output"/f"amv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        project_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, project_out)
        _status("log", "\n".join(log_lines[-50:]))
    except Exception as e:
        import traceback
        log_lines.append(f"\nERROR: {e}"); log_lines.append(traceback.format_exc()[-500:])
        _status("log", "\n".join(log_lines[-50:])); _status("step", "error")
    _status("running", False)


def start_pipeline(music, video, max_clips, drum_threshold, cut_frequency, use_vlm, progress=gr.Progress()):
    global STATUS_FILE; STATUS_FILE = Path(tempfile.mktemp(suffix=".json"))
    if music is None: yield None, "Upload music file.", "", False; return
    if video is None: yield None, "Upload video file.", "", False; return
    thread = threading.Thread(target=run_pipeline, args=(music, video, max_clips, drum_threshold, cut_frequency, use_vlm), daemon=True)
    _status("running", True); _status("step", "starting"); thread.start()
    while thread.is_alive():
        s = _read_status()
        progress(s.get("progress", 0)/100, desc=s.get("step",""))
        time.sleep(0.5)
        yield None, s.get("log",""), s.get("step",""), True
    s = _read_status(); out = s.get("output", None)
    if out and Path(out).exists(): yield out, s.get("log",""), "Complete!", False
    else: yield None, s.get("log",""), f"Error: {s.get('step','')}", False
    if STATUS_FILE and STATUS_FILE.exists(): STATUS_FILE.unlink(missing_ok=True)


def cancel_run():
    CANCEL_FLAG.set(); _status("log", "\nCancelled"); _status("step", "cancelled"); _status("running", False)


css = "#log-box { height: 300px; font-family: monospace; font-size: 12px; background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; }"

with gr.Blocks(css=css, theme=gr.themes.Soft(primary_hue="blue"), title="AMV Auto-Edit Studio") as demo:
    gr.Markdown("# AMV Auto-Edit Studio\nMusic-synced anime music video auto-editing")
    with gr.Row():
        with gr.Column(scale=1):
            music_input = gr.File(label="Music File", file_types=[".mp3",".m4a",".wav",".flac",".ogg"])
            video_input = gr.File(label="Video File", file_types=[".mp4",".mkv",".avi",".mov",".webm"])
            with gr.Accordion("Settings", open=False):
                max_clips = gr.Slider(20, 150, 60, 5, label="Max Clips")
                use_vlm = gr.Checkbox(value=True, label="VLM (GPU + ComfyUI needed)")
            run_btn = gr.Button("\u25b6 Start", variant="primary", size="lg")
            cancel_btn = gr.Button("\u23f9 Cancel", variant="stop")
        with gr.Column(scale=1):
            step_display = gr.Textbox(label="Status", interactive=False)
            log_output = gr.Textbox(label="Log", elem_id="log-box", interactive=False, lines=15)
    video_output = gr.Video(label="Output", width=640, height=360)

    ev = run_btn.click(fn=start_pipeline,
        inputs=[music_input, video_input, max_clips, gr.State(6), gr.State("Medium (~2.5s)"), use_vlm],
        outputs=[video_output, log_output, step_display, cancel_btn], queue=True, concurrency_limit=1)
    cancel_btn.click(fn=cancel_run, cancels=[ev])


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--share", action="store_true", help="Public link")
    p.add_argument("--port", type=int, default=7860)
    p.add_argument("--host", default="127.0.0.1")
    a = p.parse_args()
    print(f"AMV Web UI: http://{a.host}:{a.port}" + (" (+ public link)" if a.share else ""))
    demo.queue(default_concurrency_limit=1).launch(server_name=a.host, server_port=a.port, share=a.share)
