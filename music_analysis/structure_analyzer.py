"""Pure numpy/scipy song structure analyzer - improved chorus/drop detection"""
import json
import numpy as np
from pathlib import Path

class StructureAnalyzer:
    def __init__(self, hop_length=512, fft_size=2048):
        self.hop_length = hop_length
        self.fft_size = fft_size

    def analyze(self, audio_path, beats=None):
        from utils.audio_loader import load_audio
        y, sr = load_audio(audio_path)
        duration = len(y) / sr
        bpm_hint = None
        if beats and len(beats) > 4:
            bpm_hint = 60.0 / (beats[-1] - beats[-5]) * 4
        hop, n_fft = self.hop_length, self.fft_size
        frames = 1 + (len(y) - n_fft) // hop
        S = np.zeros((n_fft // 2 + 1, frames), dtype=np.float32)
        window = np.hanning(n_fft).astype(np.float32)
        for i in range(frames):
            start_i = i * hop
            frame = y[start_i:start_i + n_fft]
            if len(frame) < n_fft:
                frame = np.pad(frame, (0, n_fft - len(frame)))
            S[:, i] = np.abs(np.fft.rfft((frame * window).astype(np.float32)))
        times = np.arange(frames) * hop / sr
        rms_full = np.sqrt(np.mean(S ** 2, axis=0))
        if bpm_hint and 60 < bpm_hint < 200:
            min_section = max(8, 60.0 / bpm_hint * 8)
        else:
            min_section = 10.0
        energy_diff = np.abs(np.diff(rms_full, prepend=rms_full[0]))
        threshold = np.percentile(energy_diff, 92)
        bf = np.where(energy_diff > threshold)[0]
        boundaries = [0.0]
        for fb in bf:
            bt = times[fb]
            if bt - boundaries[-1] >= min_section:
                boundaries.append(round(float(bt), 2))
        if duration - boundaries[-1] >= 2.0:
            boundaries.append(round(float(duration), 2))
        else:
            boundaries[-1] = round(float(duration), 2)
        sections = []
        for i in range(len(boundaries) - 1):
            sf_i = min(int(boundaries[i] * sr / hop), len(rms_full) - 1)
            ef_i = min(int(boundaries[i+1] * sr / hop) + 1, len(rms_full))
            seg_rms = rms_full[sf_i:ef_i]
            avg_e = float(np.mean(seg_rms)) if len(seg_rms) > 0 else 1e-6
            stype = self._classify(i, len(boundaries) - 1, boundaries[i], boundaries[i+1], avg_e, rms_full)
            ne = max(1, min(10, round(avg_e / (np.max(rms_full) + 1e-6) * 10)))
            sections.append({"start": boundaries[i], "end": boundaries[i+1], "type": stype, "energy": ne})
        return sections

    def _classify(self, idx, total, start, end, energy, all_rms):
        ratio = idx / total
        norm_e = energy / (np.median(all_rms) + 1e-6)
        dur = end - start
        if idx == 0: return "intro"
        if idx == total - 1: return "outro"
        if norm_e > 1.5 and ratio > 0.3 and dur >= 6: return "drop"
        if norm_e > 1.1 and dur >= 8: return "chorus"
        if norm_e < 0.9 and 0.25 < ratio < 0.75 and dur >= 6: return "bridge"
        return "verse"

    def save(self, data, output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
