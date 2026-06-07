"""Timeline planner - cuts only on drum hits for natural rhythm"""
import json, random
from pathlib import Path
from . import rules


class TimelinePlanner:
    def __init__(self):
        self.used_clips = {}
        self.used_characters = []

    def plan(self, beats_data, structure_data, clips_data):
        beats = beats_data["beats"]
        bpm = beats_data["bpm"]
        drum_scores = beats_data.get("drum_scores", [5] * len(beats))
        downbeats = set(beats_data.get("downbeats", beats[:len(beats)//2]))
        strong_beats = set(beats_data.get("strong_beats", []))
        
        self.used_clips.clear()
        self.used_characters.clear()
        clip_map = {c["clip_id"]: c for c in clips_data}
        timeline = []

        for section in structure_data:
            section_start, section_end = section["start"], section["end"]
            section_type = section["type"]

            # Find beats in this section
            section_beats = [(i, bt) for i, bt in enumerate(beats) if section_start <= bt < section_end]
            if not section_beats:
                continue

            strategy = rules.select_cut_strategy(section_type, section["energy"])
            info = rules.CUT_STRATEGIES[strategy]
            target_gap = info["beats_per_clip"]  # target beat gap between cuts
            
            available = [c for c in clips_data if c["clip_id"] not in self.used_clips]
            if not available:
                available = clips_data

            i = 0
            while i < len(section_beats):
                beat_idx, beat_time = section_beats[i]
                
                # Find the best cut point: look ahead for a drum hit
                cut_idx = i
                beats_consumed = 0
                for j in range(i, len(section_beats)):
                    beats_consumed += 1
                    if beats_consumed >= target_gap:
                        # Check if this beat is a drum hit
                        bj = section_beats[j][0]
                        if bj < len(drum_scores) and drum_scores[bj] >= 6:
                            cut_idx = j
                            break
                        # If no drum hit found, cut at next strong beat
                        if beats_consumed >= target_gap * 2:
                            cut_idx = j
                            break
                
                # End time for this clip
                if cut_idx + 1 < len(section_beats):
                    end_time = section_beats[cut_idx + 1][1]
                else:
                    end_time = section_end
                
                # Pick the clip
                best_clip = self._select_best_clip(available, section, beat_time)
                if not best_clip:
                    i = cut_idx + 1
                    continue

                clip_id = best_clip["clip_id"]
                clip_duration = best_clip.get("duration", 4.0)
                entry_duration = end_time - beat_time
                
                # Calculate clip offset (where in the clip to start)
                use_count = self.used_clips.get(clip_id, 0)
                energy = drum_scores[beat_idx] if beat_idx < len(drum_scores) else 5
                energy_weight = energy / 10.0
                
                if use_count == 0:
                    clip_offset = clip_duration * random.uniform(0.05, 0.2)
                else:
                    r_seed = (hash(clip_id) + use_count * 7) % 100 / 100.0
                    clip_offset = clip_duration * min(0.2 + r_seed * 0.5 * (0.5 + energy_weight), 0.8)
                
                max_offset = max(0, clip_duration - entry_duration - 0.1)
                clip_offset = min(clip_offset, max_offset)

                self.used_clips[clip_id] = use_count + 1
                self.used_characters.append(best_clip.get("character", ""))
                if len(self.used_characters) > 20:
                    self.used_characters = self.used_characters[-10:]

                timeline.append({
                    "start": round(beat_time, 3),
                    "end": round(end_time, 3),
                    "duration": round(entry_duration, 3),
                    "clip": clip_id,
                    "file": best_clip["file"],
                    "section": section_type,
                    "clip_offset": round(clip_offset, 3),
                    "drum_hit": beat_idx < len(drum_scores) and drum_scores[beat_idx] >= 6,
                    "is_downbeat": round(beat_time, 3) in {round(b, 3) for b in list(downbeats)[:len(section_beats)]},
                })

                if best_clip in available:
                    available.remove(best_clip)
                if not available:
                    available = [c for c in clips_data if c["clip_id"] not in self.used_clips]
                    if not available:
                        self.used_clips.clear()
                        available = clips_data

                i = cut_idx + 1

        return timeline

    def _select_best_clip(self, clips, section, beat_time):
        scored = [(rules.calculate_clip_score(c, section, self.used_clips, self.used_characters), c) for c in clips]
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            return random.choice(scored[:3])[1] if len(scored) >= 3 else scored[0][1]
        return None

    def save(self, timeline, output_path):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
