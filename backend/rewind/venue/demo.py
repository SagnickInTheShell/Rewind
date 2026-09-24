"""Builder for the demo venue (``data/venues/demo_venue.json``).

A 30 m × 20 m plaza split into a 3×3 grid (rows A..C north→south, columns 1..3 west→east).
World frame: x east, y south, origin at the north-west corner.
"""

from __future__ import annotations

from rewind.schemas.venue import OUTSIDE, CameraCalibration, Point, Portal, Venue, Wall, Zone

WIDTH, HEIGHT = 30.0, 20.0
ROWS = "ABC"

# Synthetic top-down camera used by scripts/render_synthetic_video.py: 1280x720 frame,
# 32 px per metre, venue drawn with its north-west corner at pixel (160, 40).
PX_PER_M = 32.0
ORIGIN_PX = (160.0, 40.0)
FRAME_SIZE = (1280, 720)


def _p(x: float, y: float) -> Point:
    return Point(x=round(x, 4), y=round(y, 4))


def world_to_synthetic_px(x: float, y: float) -> tuple[float, float]:
    return ORIGIN_PX[0] + x * PX_PER_M, ORIGIN_PX[1] + y * PX_PER_M


def build_demo_venue() -> Venue:
    cw, ch = WIDTH / 3, HEIGHT / 3
    zones = []
    kinds = {"A2": "entry", "C2": "exit", "C3": "gate_area"}
    for r, row in enumerate(ROWS):
        for c in range(3):
            zid = f"{row}{c + 1}"
            x0, y0 = c * cw, r * ch
            zones.append(Zone(zone_id=zid, name=f"Zone {zid}", kind=kinds.get(zid, "floor"),  # type: ignore[arg-type]
                              polygon=[_p(x0, y0), _p(x0 + cw, y0), _p(x0 + cw, y0 + ch), _p(x0, y0 + ch)]))

    portals: list[Portal] = []
    # Internal full-width openings between horizontally adjacent zones.
    for r, row in enumerate(ROWS):
        for c in range(2):
            a, b = f"{row}{c + 1}", f"{row}{c + 2}"
            x = (c + 1) * cw
            portals.append(Portal(portal_id=f"C_{a}_{b}", name=f"{a}–{b}", from_zone=a, to_zone=b,
                                  segment=(_p(x, r * ch), _p(x, (r + 1) * ch)), width_m=round(ch, 4),
                                  kind="corridor"))
    # Vertically adjacent zones; B1–C1 is partly walled (x 0..6 m) to create a natural bottleneck.
    for r in range(2):
        for c in range(3):
            a, b = f"{ROWS[r]}{c + 1}", f"{ROWS[r + 1]}{c + 1}"
            y = (r + 1) * ch
            x0, x1 = c * cw, (c + 1) * cw
            if a == "B1":
                x0 = 6.0
            portals.append(Portal(portal_id=f"C_{a}_{b}", name=f"{a}–{b}", from_zone=a, to_zone=b,
                                  segment=(_p(x0, y), _p(x1, y)), width_m=round(x1 - x0, 4), kind="corridor"))

    portals += [
        Portal(portal_id="GATE_A", name="Gate A", from_zone=OUTSIDE, to_zone="A2",
               segment=(_p(13.0, 0.0), _p(17.0, 0.0)), width_m=4.0, bidirectional=False, kind="gate"),
        Portal(portal_id="GATE_B", name="Gate B", from_zone="C2", to_zone=OUTSIDE,
               segment=(_p(13.5, HEIGHT), _p(16.5, HEIGHT)), width_m=3.0, bidirectional=False, kind="gate"),
        Portal(portal_id="GATE_C", name="Gate C", from_zone="C3", to_zone=OUTSIDE,
               segment=(_p(WIDTH, 15.0), _p(WIDTH, 18.5)), width_m=3.5, is_open=False,
               bidirectional=False, kind="gate"),
    ]

    walls = [
        # north wall with Gate A opening
        Wall(a=_p(0, 0), b=_p(13.0, 0)), Wall(a=_p(17.0, 0), b=_p(WIDTH, 0)),
        # east wall with Gate C opening
        Wall(a=_p(WIDTH, 0), b=_p(WIDTH, 15.0)), Wall(a=_p(WIDTH, 18.5), b=_p(WIDTH, HEIGHT)),
        # south wall with Gate B opening
        Wall(a=_p(WIDTH, HEIGHT), b=_p(16.5, HEIGHT)), Wall(a=_p(13.5, HEIGHT), b=_p(0, HEIGHT)),
        # west wall
        Wall(a=_p(0, HEIGHT), b=_p(0, 0)),
        # partial wall between B1 and C1
        Wall(a=_p(0, 2 * ch), b=_p(6.0, 2 * ch)),
    ]

    corners_w = [(0.0, 0.0), (WIDTH, 0.0), (WIDTH, HEIGHT), (0.0, HEIGHT), (15.0, 10.0)]
    calib = CameraCalibration(
        image_points=[_p(*world_to_synthetic_px(x, y)) for x, y in corners_w],
        world_points=[_p(x, y) for x, y in corners_w],
    )
    return Venue(venue_id="demo_venue", name="Demo Plaza (30 m × 20 m)",
                 bounds=(_p(0, 0), _p(WIDTH, HEIGHT)), zones=zones, portals=portals, walls=walls,
                 sources=["A2"], sinks=["C2", "C3"], calibration=calib)
