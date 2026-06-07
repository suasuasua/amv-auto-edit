"""
Clip analyzer - supports mock and local VLM backends.
When ComfyUI Python env is available, uses Qwen2-VL-2B for real AI analysis.
"""
import json, subprocess, sys, os
from pathlib import Path

# ComfyUI Python path
COMFYUI_PYTHON = r"P:\ComfyUI_windows_portable\python_embeded\python.exe"
VLM_SCRIPT = Path(__file__).parent / "local_vlm.py"
HF_CACHE = Path(__file__).parent.parent / "vlm_cache"


def _comfyui_available() -> bool:
    return Path(COMFYUI_PYTHON).exists() and VLM_SCRIPT.exists()


def _run_vlm_subprocess(clips: list, frames_dir: str, model: str = "Qwen/Qwen2-VL-2B-Instruct") -> list:
    """Run VLM analyzer in ComfyUI Python as subprocess"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(clips, f, ensure_ascii=False)
        input_path = f.name
    
    output_path = input_path.replace(".json", "_out.json")
    
    env = os.environ.copy()
    env["HF_HOME"] = str(HF_CACHE)
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    
    cmd = [
        COMFYUI_PYTHON, str(VLM_SCRIPT),
        "--clips", input_path,
        "--frames", frames_dir,
        "--output", output_path,
        "--model", model,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    
    if result.returncode != 0:
        raise RuntimeError(f"VLM failed: {result.stderr[-500:]}")
    
    labeled = json.loads(Path(output_path).read_text(encoding="utf-8"))
    
    # Cleanup temp files
    Path(input_path).unlink(missing_ok=True)
    Path(output_path).unlink(missing_ok=True)
    
    return labeled


class ClipAnalyzer:
    def __init__(self, api_key: str = None, model: str = "gpt-4o", use_local_vlm: bool = True, vlm_model: str = "Qwen/Qwen2-VL-2B-Instruct"):
        self.api_key = api_key
        self.model = model
        self.use_local_vlm = use_local_vlm and _comfyui_available()
        self.vlm_model = vlm_model
        if use_local_vlm and not _comfyui_available():
            print("  Note: ComfyUI Python not found, using mock labels", flush=True)

    def analyze_frame(self, frame_path: str) -> dict:
        """Mock single frame analysis (fallback when no VLM)"""
        return {
            "anime": "unknown", "character": "unknown", "action": "unknown",
            "emotion": "neutral", "energy": 5, "motion": 5, "visual_impact": 5,
            "tags": []
        }

    def batch_analyze(self, clip_list: list, frames_dir: str) -> list:
        """Batch analyze clips - uses local VLM when available"""
        if self.use_local_vlm:
            print(f"  Using local VLM ({self.model})...", flush=True)
            try:
                return _run_vlm_subprocess(clip_list, frames_dir, self.vlm_model)
            except Exception as e:
                print(f"  VLM failed ({e}), falling back to mock", flush=True)

        print("  Using mock analyzer...", flush=True)
        from .frame_extractor import FrameExtractor
        fe = FrameExtractor()
        
        results = []
        for clip in clip_list:
            clip_id = clip["clip_id"]
            duration = clip["duration"]
            
            frames = fe.extract_key_frames(clip["file"], frames_dir, clip_id, duration, num_frames=2)
            if not frames:
                mid = fe.extract_middle_frame(clip["file"], str(Path(frames_dir) / f"{clip_id}_mid.jpg"), duration)
                frames = [mid] if mid else []
            
            label = {"anime":"unknown","character":"unknown","action":"unknown","emotion":"neutral",
                     "energy":5,"motion":5,"visual_impact":5,"character_focus":5,"tags":[]}
            for f in frames:
                lbl = self.analyze_frame(f)
                if lbl.get("anime") != "unknown":
                    label = lbl; break
            
            score = round(0.4*label["energy"] + 0.3*label["motion"] + 0.3*label["visual_impact"], 2)
            results.append({"clip_id":clip_id,"file":clip.get("file",""),"duration":duration,**label,"score":score})
        
        return results

    def save(self, data: list, output_path: str):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
