"""Named screen regions ("visual anchors"). The Director assigns every object a
zone; scene code calls ``place_in_zone`` so things land where planned and are
shrunk to fit instead of spilling off-screen or onto each other.

Pure geometry — no manim import — so it is unit-testable without a renderer.
Default frame is ManimCE's 14.22 x 8 units centered on the origin.
"""

from __future__ import annotations

from dataclasses import dataclass

FRAME_WIDTH = 8.0 * 16 / 9
FRAME_HEIGHT = 8.0
MARGIN = 0.4          # keep content off the very edge
BAND = 1.0            # height of the title / caption bands
GAP = 0.2             # gap between bands and the main area, and between LEFT/RIGHT


@dataclass(frozen=True)
class Zone:
    name: str
    x0: float
    x1: float
    y0: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def contains(self, x0: float, x1: float, y0: float, y1: float, tol: float = 1e-3) -> bool:
        return (x0 >= self.x0 - tol and x1 <= self.x1 + tol
                and y0 >= self.y0 - tol and y1 <= self.y1 + tol)


def build_zones(frame_width: float = FRAME_WIDTH, frame_height: float = FRAME_HEIGHT) -> dict[str, Zone]:
    hw, hh = frame_width / 2, frame_height / 2
    left, right = -hw + MARGIN, hw - MARGIN
    top, bottom = hh - MARGIN, -hh + MARGIN
    main_top, main_bottom = top - BAND - GAP, bottom + BAND + GAP
    return {
        "FULL": Zone("FULL", left, right, bottom, top),
        "TOP": Zone("TOP", left, right, top - BAND, top),
        "BOTTOM": Zone("BOTTOM", left, right, bottom, bottom + BAND),
        "CENTER": Zone("CENTER", left, right, main_bottom, main_top),
        "LEFT": Zone("LEFT", left, -GAP / 2, main_bottom, main_top),
        "RIGHT": Zone("RIGHT", GAP / 2, right, main_bottom, main_top),
    }


ZONES = build_zones()
ZONE_NAMES = tuple(ZONES)


def fit_scale(obj_width: float, obj_height: float, zone: Zone, padding: float = 0.1,
              allow_grow: bool = False) -> float:
    """Scale factor that makes an object of the given size fit inside ``zone``."""
    avail_w, avail_h = zone.width - 2 * padding, zone.height - 2 * padding
    if obj_width <= 0 and obj_height <= 0:
        return 1.0
    factors = []
    if obj_width > 0:
        factors.append(avail_w / obj_width)
    if obj_height > 0:
        factors.append(avail_h / obj_height)
    s = min(factors)
    return s if (allow_grow or s < 1.0) else 1.0
