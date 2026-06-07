"""Beat analyzer with drum hit detection"""
import json, subprocess, tempfile
import numpy as np
from scipy.signal import find_peaks, butter, filtfilt
from pathlib import Path
from utils.audio_loader import load_audio


class BeatAnalyzer:
    def __init__(self, hop_length=512, fft_size=2048):
        self.hop_length = hop_length
        self.fft_size = fft_size

    def analyze(self, audio_path):
        y, sr = load_audio(audio_path, target_sr=22050)
        duration = len(y) / sr
        onset_env, S, times, freqs = self._compute_features(y, sr)
        bpm, beat_frames = self._estimate_tempo_and_beats(onset_env, sr)
        beat_times = beat_frames * self.hop_length / sr
        beat_energies = self._compute_beat_energies(y, sr, beat_times)
        drum_scores = self._compute_drum_scores(onset_env, S, freqs, sr, beat_frames)
        
        drum_threshold = np.percentile(drum_scores, 60) if len(drum_scores) > 0 else 5
        downbeats = [round(float(beat_times[i]), 4) for i in range(len(beat_times)) if drum_scores[i] >= drum_threshold]
        
        strong_threshold = np.percentile(drum_scores, 80) if len(drum_scores) > 0 else 8
        strong_beats = [round(float(beat_times[i]), 4) for i in range(len(beat_times)) if drum_scores[i] >= strong_threshold]
        
        return {
            "bpm": round(float(bpm), 1),
            "beats": [round(float(t), 4) for t in beat_times],
            "beat_energies": [max(1, min(10, int(e))) for e in beat_energies],
            "drum_scores": [max(1, min(10, int(round(d)))) for d in drum_scores],
            "downbeats": downbeats,
            "strong_beats": strong_beats,
            "duration": float(duration)
        }

    def _compute_features(self, y, sr):
        hop, n_fft = self.hop_length, self.fft_size
        frames = 1 + (len(y) - n_fft) // hop
        S = np.zeros((n_fft // 2 + 1, frames))
        for i in range(frames):
            start = i * hop
            frame = y[start:start + n_fft]
            if len(frame) < n_fft:
                frame = np.pad(frame, (0, n_fft - len(frame)))
            S[:, i] = np.abs(np.fft.rfft(frame * np.hanning(n_fft)))
        flux = np.zeros(frames)
        diff = np.diff(S, axis=1)
        flux[1:] = np.sum(np.maximum(diff, 0), axis=0)
        if len(flux) > 5:
            b = butter(4, 0.3, btype="low", output="ba")
            flux = filtfilt(b[0], b[1], flux)
        times = np.arange(frames) * hop / sr
        freqs = np.fft.rfftfreq(n_fft, 1 / sr)
        return flux, S, times, freqs

    def _compute_drum_scores(self, onset_env, S, freqs, sr, beat_frames):
        n_beats = len(beat_frames)
        if n_beats == 0:
            return np.array([])
        drum_scores = []
        for i in range(n_beats):
            bf = beat_frames[i]
            bf_int = int(min(bf, len(onset_env)-1)) if bf < len(onset_env) else 0
            onset_val = onset_env[bf_int]
            bf_int2 = int(min(bf, S.shape[1]-1)) if bf < S.shape[1] else S.shape[1]-1
            frame = bf_int2
            low_mask = (freqs >= 60) & (freqs <= 150)
            low_energy = np.mean(S[low_mask, frame]) if np.any(low_mask) else 0
            mid_mask = (freqs >= 200) & (freqs <= 500)
            mid_energy = np.mean(S[mid_mask, frame]) if np.any(mid_mask) else 0
            high_mask = (freqs >= 8000)
            high_energy = np.mean(S[high_mask, frame]) if np.any(high_mask) else 0
            score = (0.4 * onset_val / (np.max(onset_env) + 1e-10) +
                     0.3 * low_energy / (np.max(S[:, frame]) + 1e-10) +
                     0.2 * mid_energy / (np.max(S[:, frame]) + 1e-10) +
                     0.1 * high_energy / (np.max(S[:, frame]) + 1e-10))
            drum_scores.append(score)
        drum_scores = np.array(drum_scores)
        if np.max(drum_scores) > 0:
            drum_scores = drum_scores / np.max(drum_scores) * 10
        else:
            drum_scores = np.ones(n_beats) * 5
        return np.clip(drum_scores, 1, 10)

    def _estimate_tempo_and_beats(self, onset_env, sr):
        n = len(onset_env)
        if n < 10:
            return 120.0, np.array([0.0])
        ac = np.correlate(onset_env - onset_env.mean(), onset_env - onset_env.mean(), mode="full")
        ac = ac[n - 1:] / (n - np.arange(n))
        hop_sec = self.hop_length / sr
        hop_sr = sr / self.hop_length
        min_lag = int(hop_sr / 5.0)
        max_lag = int(hop_sr / 0.5)
        max_lag = min(max_lag, len(ac) - 1)
        if min_lag >= max_lag:
            bpm = 120.0; interval = 60.0 / bpm / hop_sec
            bf = np.arange(0, n, interval).astype(int); bf = bf[bf < n]
            return bpm, bf.astype(float)
        search = ac[min_lag:max_lag + 1]
        peaks, _ = find_peaks(search, height=np.percentile(search, 75))
        peaks = peaks + min_lag
        best_bpm = 120.0; best_lag = int(hop_sr / 2.0)
        if len(peaks) > 0:
            candidates = [(pk, 60.0/(pk/hop_sr), ac[pk]) for pk in peaks]
            best_score = -1
            for lag, cb, amp in candidates:
                score = amp
                if 80 <= cb <= 180: score *= 2.0
                elif cb < 40 or cb > 300: score *= 0.1
                hl = max(min_lag, lag // 2)
                if hl != lag and hl <= max_lag:
                    hb = 60.0/(hl/hop_sr)
                    if 80 <= hb <= 220: score = max(score, ac[hl] * 1.5)
                if score > best_score:
                    best_score = score; best_lag = lag; best_bpm = cb
        if best_bpm < 60:
            hl = best_lag // 2
            if hl >= min_lag: best_lag = hl; best_bpm = 60.0/(hl/hop_sr)
        elif best_bpm > 240:
            dl = best_lag * 2
            if dl <= max_lag: best_lag = dl; best_bpm = 60.0/(dl/hop_sr)
        best_bpm = max(60.0, min(240.0, best_bpm))
        interval = 60.0 / best_bpm / hop_sec
        bf = np.arange(0, n, interval).astype(int)
        bf = bf[bf < n]
        half = max(1, int(interval) // 4)
        refined = []
        for fb in bf:
            lo = max(0, fb - half); hi = min(n, fb + half + 1)
            refined.append(lo + int(np.argmax(onset_env[lo:hi])) if hi > lo else fb)
        return best_bpm, np.array(refined, dtype=float)

    def _compute_beat_energies(self, y, sr, beat_times):
        energies = []
        for i in range(len(beat_times)):
            s = int(beat_times[i] * sr)
            e = int(beat_times[i + 1] * sr) if i + 1 < len(beat_times) else min(len(y), s + int(sr / 2))
            rms = float(np.sqrt(np.mean(y[s:e] ** 2))) if 0 <= s < e <= len(y) else 0
            energies.append(rms)
        if energies and max(energies) > 0:
            mx = max(energies)
            energies = [max(1, min(10, round(e / mx * 10))) for e in energies]
        else:
            energies = [5] * len(beat_times)
        return np.array(energies, dtype=int)

    def save(self, data, output_path):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
