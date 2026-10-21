"""Versioned public edit contracts. The frozen study profile remains the default."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityProfile:
    name: str
    capabilities: dict
    initial: dict
    max_repairs: int = 2
    trial_limit_seconds: int = 120
    clarify_repairs: bool = False

    @property
    def fields(self):
        return tuple(self.capabilities)

    @property
    def categorical_fields(self):
        return tuple(name for name in self.fields if name != "scale")


STUDY_PROFILE = CapabilityProfile(
    "study-v1",
    {"jacket_color": ["blue", "orange", "green", "gray", "red", "purple"],
     "accessory": ["none", "hat", "glasses"],
     "scale": {"min": .85, "max": 1.15, "step": .05}},
    {"jacket_color": "blue", "accessory": "none", "scale": 1.0},
)
AVATAR_DEFAULTS = {
    "liang": {"avatar_id": "liang", "outfit": "suit", "jacket_color": "blue",
              "accessory": "glasses", "scale": 1.0},
    "nailong": {"avatar_id": "nailong", "outfit": "none", "jacket_color": "yellow",
                "accessory": "none", "scale": 1.0},
}
WHOLE_REPLACEMENT_PHRASES = (
    "全部替换", "整体替换", "全部换掉", "整个换掉", "全都换掉", "全换",
    "replace everything", "replace all", "whole replacement",
)
DEMO_PROFILE = CapabilityProfile(
    "avatar-demo-v1",
    {**STUDY_PROFILE.capabilities,
     "jacket_color": [*STUDY_PROFILE.capabilities["jacket_color"], "yellow"],
     "avatar_id": ["liang", "nailong"],
     "outfit": ["suit", "sport", "none"]},
    AVATAR_DEFAULTS["liang"],
    max_repairs=12, trial_limit_seconds=600, clarify_repairs=True,
)
PROFILES = {profile.name: profile for profile in (STUDY_PROFILE, DEMO_PROFILE)}
