"""Clip matching rules - adjusted for natural viewing rhythm"""
from typing import Callable

# Section-based clip priority rules
SECTION_RULES = {
    "intro": {
        "priority_tags": ["landscape", "slow", "entrance"],
        "max_energy": 5,
        "description": "Slow establishing shots for intro"
    },
    "verse": {
        "priority_tags": ["dialogue", "walking"],
        "max_energy": 7,
        "description": "Dialogue/story scenes for verse"
    },
    "chorus": {
        "priority_tags": ["battle", "action", "running"],
        "min_energy": 5,
        "description": "High-energy clips for chorus"
    },
    "bridge": {
        "priority_tags": ["closeup", "sad", "dramatic"],
        "max_energy": 6,
        "description": "Dramatic moments for bridge"
    },
    "drop": {
        "priority_tags": ["explosion", "transform", "special"],
        "min_energy": 7,
        "description": "Most intense clips for drop"
    },
    "outro": {
        "priority_tags": ["landscape", "slow", "end"],
        "max_energy": 4,
        "description": "Calm ending shots"
    }
}

# Cut strategies - slower pacing for natural viewing
# BPM=92 => 1 beat ~0.65s
CUT_STRATEGIES = {
    "sparse": {
        "description": "8 beats = 1 clip (~5.2s) - slow sections",
        "beats_per_clip": 8,
        "min_score_gap": 3
    },
    "normal": {
        "description": "6 beats = 1 clip (~3.9s) - narrative sections",
        "beats_per_clip": 6,
        "min_score_gap": 2
    },
    "intense": {
        "description": "4 beats = 1 clip (~2.6s) - energetic sections",
        "beats_per_clip": 4,
        "min_score_gap": 1
    },
    "climax": {
        "description": "2 beats = 1 clip (~1.3s) - peak moments",
        "beats_per_clip": 2,
        "min_score_gap": 0
    }
}


def select_cut_strategy(section_type: str, energy: int) -> str:
    """Select cut strategy based on section type"""
    if section_type == "intro":
        return "sparse"
    elif section_type == "outro":
        return "sparse"
    elif section_type == "verse":
        return "normal"
    elif section_type == "bridge":
        return "sparse"
    elif section_type == "chorus":
        return "normal"
    elif section_type == "drop":
        return "intense"
    return "normal"


def calculate_clip_score(clip: dict, section: dict, used_clips: set, used_characters: list) -> float:
    """Score a clip for a given section"""
    score = clip.get("score", 5)

    # Energy mismatch penalty
    energy_diff = abs(clip.get("energy", 5) - section["energy"])
    score -= energy_diff * 0.5

    # Penalty for already-used clips
    if clip["clip_id"] in used_clips:
        score -= 50

    # Penalty for same character in consecutive clips
    if used_characters and clip.get("character") == used_characters[-1]:
        score -= 5

    # Priority tag bonus
    section_rules = SECTION_RULES.get(section["type"], {})
    priority_tags = section_rules.get("priority_tags", [])
    clip_tags = set(clip.get("tags", []))
    matched = len(clip_tags & set(priority_tags))
    score += matched * 2

    return score
