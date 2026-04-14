"""Imported LED animations — 27 effects ported from led_sim.py.

Registers all effects into a single IMPORTED_EFFECTS dict.
"""

from .classic import CLASSIC_EFFECTS
from .ambient_a import AMBIENT_A_EFFECTS
from .ambient_b import AMBIENT_B_EFFECTS
from .sound import SOUND_EFFECTS

IMPORTED_EFFECTS = {
  **CLASSIC_EFFECTS,
  **AMBIENT_A_EFFECTS,
  **AMBIENT_B_EFFECTS,
  **SOUND_EFFECTS,
}
