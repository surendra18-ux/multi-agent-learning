"""
storage.py — load/save learner_data.json
"""

import json
import os
from typing import Any, Dict

DATA_FILE = "learner_data.json"

DEFAULT_PROFILE: Dict[str, Any] = {
    "learner_id": "",
    "goal": "",
    "topics": [],
    "current_topic_index": 0,
}


def load_profile() -> Dict[str, Any]:
    """Load the learner profile from disk, or return a fresh default."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Back-fill any missing top-level keys
        for key, value in DEFAULT_PROFILE.items():
            data.setdefault(key, value)
        return data
    return dict(DEFAULT_PROFILE)


def save_profile(profile: Dict[str, Any]) -> None:
    """Persist the learner profile to disk."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def profile_exists() -> bool:
    """Return True if a saved profile already exists on disk."""
    return os.path.exists(DATA_FILE)


def reset_profile() -> None:
    """Delete the saved profile file (start fresh)."""
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
