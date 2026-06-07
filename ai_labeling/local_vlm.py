"""
Local VLM analyzer - runs under ComfyUI Python env.
Usage: python local_vlm.py --clips clips.json --frames frames/ --output output.json
"""
import os, sys, json, time
from pathlib import Path

def load_model(model_name: str = "Qwen/Qwen2-VL-2B-Instruct"):
    """Load VLM model (cached)"""
    import torch
    from transformers import Qwen2VLForConditionalGeneration, Qwen2VLProcessor

    print(f"Loading {model_name}...", flush=True)
    t0 = time.time()
    processor = Qwen2VLProcessor.from_pretrained(model_name, trust_remote_code=True)
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_name, dtype="auto", device_map="auto", trust_remote_code=True)
    print(f"Loaded on {model.device} in {time.time()-t0:.1f}s", flush=True)
    return model, processor


def analyze_frame(model, processor, frame_path: str) -> dict:
    """Analyze single frame with VLM, return structured labels"""
    from PIL import Image
    import torch

    img = Image.open(frame_path).convert("RGB")

    prompt = (
        "Analyze this anime clip frame. Return JSON with:\n"
        "- anime: anime name\n"
        "- character: main character name\n"
        "- action: what the character is doing\n"
        "- emotion: one word (happy/sad/angry/neutral/surprised/calm/fear)\n"
        "- energy: scene energy level 1-10\n"
        "- motion: motion intensity 1-10\n"
        "- visual_impact: visual impact 1-10\n"
        "- tags: array of short keywords (e.g. fight, action, closeup, magic, calm)\n\n"
        "ONLY valid JSON, no other text."
    )

    messages = [{"role": "user", "content": [
        {"type": "image", "image": img},
        {"type": "text", "text": prompt}
    ]}]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], padding=True, return_tensors="pt").to("cuda")

    generated = model.generate(**inputs, max_new_tokens=256, temperature=0.1)
    response = processor.decode(generated[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    # Parse JSON from response
    try:
        if "{" in response:
            json_str = response[response.index("{"):response.rindex("}") + 1]
            result = json.loads(json_str)
        else:
            result = json.loads(response)
    except (json.JSONDecodeError, ValueError):
        import re
        energy = int(re.search(r"energy.*?(\d+)", response, re.I).group(1)) if re.search(r"energy.*?(\d+)", response, re.I) else 5
        motion = int(re.search(r"motion.*?(\d+)", response, re.I).group(1)) if re.search(r"motion.*?(\d+)", response, re.I) else 5
        impact = int(re.search(r"(?:visual_impact|impact).*?(\d+)", response, re.I).group(1)) if re.search(r"(?:visual_impact|impact).*?(\d+)", response, re.I) else 5
        result = {"anime":"unknown","character":"unknown","action":"unknown","emotion":"neutral",
                  "energy": min(10,max(1,energy)), "motion": min(10,max(1,motion)),
                  "visual_impact": min(10,max(1,impact)), "tags": []}

    # Ensure all fields exist
    defaults = {"anime":"unknown","character":"unknown","action":"unknown","emotion":"neutral",
                "energy":5,"motion":5,"visual_impact":5,"character_focus":5,"tags":[]}
    for k, v in defaults.items():
        if k not in result:
            result[k] = v

    return result


def batch_analyze(model, processor, clips: list, frames_dir: str) -> list:
    """Batch analyze all clips"""
    frames_path = Path(frames_dir)
    results = []

    for clip in clips:
        clip_id = clip["clip_id"]
        duration = clip["duration"]

        # Find frames for this clip
        frame_files = sorted((frames_path / clip_id).glob("*.jpg")) if (frames_path / clip_id).exists() else []
        if not frame_files:
            mid = frames_path / f"{clip_id}_mid.jpg"
            if mid.exists():
                frame_files = [mid]

        label = None
        for ff in frame_files:
            try:
                lbl = analyze_frame(model, processor, str(ff))
                if lbl.get("anime") != "unknown" or lbl.get("character") != "unknown":
                    label = lbl
                    break
            except Exception as e:
                print(f"  VLM error {ff.name}: {e}", flush=True)

        if label is None:
            label = {"anime":"unknown","character":"unknown","action":"unknown","emotion":"neutral",
                     "energy":5,"motion":5,"visual_impact":5,"character_focus":5,"tags":[]}

        score = round(0.4 * label["energy"] + 0.3 * label["motion"] + 0.3 * label["visual_impact"], 2)

        results.append({
            "clip_id": clip_id,
            "file": clip.get("file", ""),
            "duration": duration,
            **label,
            "score": score
        })
        print(f"  {clip_id}: {label.get('character','?')} - {label.get('action','?')} (E={label['energy']} S={score})", flush=True)

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Local VLM clip analyzer")
    parser.add_argument("--clips", required=True, help="Clip manifest JSON path")
    parser.add_argument("--frames", required=True, help="Frames directory path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--model", default="Qwen/Qwen2-VL-2B-Instruct", help="VLM model name")
    args = parser.parse_args()

    clips = json.loads(Path(args.clips).read_text(encoding="utf-8"))
    if isinstance(clips, dict) and "clips" in clips:
        clips = clips["clips"]

    print(f"Analyzing {len(clips)} clips with {args.model}", flush=True)
    model, processor = load_model(args.model)
    results = batch_analyze(model, processor, clips, args.frames)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. Saved to {args.output}", flush=True)


if __name__ == "__main__":
    main()
