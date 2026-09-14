"""Pure mathematical profile primitives for Curve Profile Creator.

This module deliberately has no Blender dependency.  It defines the small
geometry-kernel layer used by the Blender writer in :mod:`primitives`.
Canonical profile parts are generated from dimensions and analytic cubic
Bezier approximations rather than from stored silhouettes.
"""

from dataclasses import dataclass
import math
from typing import Dict, Sequence, Tuple

from . import compound_geometry

Point2 = Tuple[float, float]


@dataclass(frozen=True)
class CubicSegment:
    p0: Point2
    h0: Point2
    h1: Point2
    p1: Point2


@dataclass(frozen=True)
class PrimitiveGeometry:
    primitive_id: str
    display_name: str
    segments: Tuple[CubicSegment, ...]
    start_tangent: Point2
    end_tangent: Point2
    start_join: str
    end_join: str
    parameters: Dict[str, float | str]
    construction: str
    straight: bool = False


def _add(a: Point2, b: Point2) -> Point2:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Point2, b: Point2) -> Point2:
    return (a[0] - b[0], a[1] - b[1])


def _mul(a: Point2, scalar: float) -> Point2:
    return (a[0] * scalar, a[1] * scalar)



def _normalise(v: Point2) -> Point2:
    length = math.hypot(v[0], v[1])
    if length < 1.0e-12:
        return (1.0, 0.0)
    return (v[0] / length, v[1] / length)


def cubic_ellipse_arc(
    center: Point2,
    radius_x: float,
    radius_y: float,
    start_angle: float,
    end_angle: float,
) -> CubicSegment:
    """Return one cubic Bezier approximation of an elliptical arc.

    The caller keeps each span at 90 degrees or less.  The construction is the
    standard circular cubic rule h = 4/3 tan(theta/4), followed by affine X/Y
    scaling for ellipses.  A signed sweep is supported.
    """
    delta = end_angle - start_angle
    if abs(delta) > math.pi / 2.0 + 1.0e-9:
        raise ValueError("Ellipse arc spans must be 90 degrees or less")

    cx, cy = center
    rx = max(abs(radius_x), 1.0e-9)
    ry = max(abs(radius_y), 1.0e-9)

    def point(theta: float) -> Point2:
        return (cx + rx * math.cos(theta), cy + ry * math.sin(theta))

    def derivative(theta: float) -> Point2:
        return (-rx * math.sin(theta), ry * math.cos(theta))

    p0 = point(start_angle)
    p1 = point(end_angle)
    d0 = derivative(start_angle)
    d1 = derivative(end_angle)
    k = (4.0 / 3.0) * math.tan(delta / 4.0)
    h0 = _add(p0, _mul(d0, k))
    h1 = _sub(p1, _mul(d1, k))
    return CubicSegment(p0, h0, h1, p1)


def _tangents(segments: Sequence[CubicSegment]) -> Tuple[Point2, Point2]:
    first = segments[0]
    last = segments[-1]
    return _normalise(_sub(first.h0, first.p0)), _normalise(_sub(last.p1, last.h1))


def _geometry(
    primitive_id: str,
    display_name: str,
    segments: Sequence[CubicSegment],
    *,
    start_join: str,
    end_join: str,
    parameters: Dict[str, float | str],
    construction: str,
    straight: bool = False,
) -> PrimitiveGeometry:
    tangents = _tangents(segments)
    return PrimitiveGeometry(
        primitive_id=primitive_id,
        display_name=display_name,
        segments=tuple(segments),
        start_tangent=tangents[0],
        end_tangent=tangents[1],
        start_join=start_join,
        end_join=end_join,
        parameters=parameters,
        construction=construction,
        straight=straight,
    )


def make_line(width: float) -> PrimitiveGeometry:
    width = max(abs(width), 1.0e-6)
    p0 = (0.0, 0.0)
    p1 = (width, 0.0)
    # Handles are only placeholders here.  The Blender writer sets VECTOR on
    # both points so Blender keeps the span exactly rectilinear.
    h0 = (width / 3.0, 0.0)
    h1 = (2.0 * width / 3.0, 0.0)
    return _geometry(
        "LINE",
        "Line / Fascia",
        [CubicSegment(p0, h0, h1, p1)],
        start_join="HARD",
        end_join="HARD",
        parameters={"width": width},
        construction="LINE",
        straight=True,
    )


def _clamp_fullness(fullness: float) -> float:
    # 1.0 is the canonical circle/ellipse conic weight.  Values below pull the
    # curve evenly toward its chord; values above pull it toward the
    # intersection of its endpoint tangents.
    return min(1.8, max(0.2, float(fullness)))


def conic_cubic(p0: Point2, tangent_intersection: Point2, p2: Point2, fullness: float) -> CubicSegment:
    """Approximate a rational quadratic conic with one editable cubic.

    ``tangent_intersection`` is the intersection of the start/end tangent
    lines.  A quarter circle/ellipse uses rational weight cos(45°).  Fullness
    scales that *conic weight*, rather than simply scaling Bezier handles.

    The cubic is solved to preserve both endpoint tangent directions and the
    exact rational-conic midpoint.  At Fullness=1 for a 90° circular arc this
    reproduces the standard kappa 0.5522847498 cubic construction.
    """
    f = _clamp_fullness(fullness)
    weight = (math.sqrt(2.0) * 0.5) * f

    # Rational quadratic midpoint at t=0.5.
    denom = 2.0 * (1.0 + weight)
    midpoint = (
        (p0[0] + p2[0] + 2.0 * weight * tangent_intersection[0]) / denom,
        (p0[1] + p2[1] + 2.0 * weight * tangent_intersection[1]) / denom,
    )

    t0 = _normalise(_sub(tangent_intersection, p0))
    t1 = _normalise(_sub(p2, tangent_intersection))

    # For a cubic with H0=P0+a*T0 and H1=P2-b*T1, matching the
    # rational-conic midpoint gives:
    #   a*T0 - b*T1 = (8/3) * (M - (P0+P2)/2)
    chord_mid = _mul(_add(p0, p2), 0.5)
    r = _mul(_sub(midpoint, chord_mid), 8.0 / 3.0)

    a00, a01 = t0[0], -t1[0]
    a10, a11 = t0[1], -t1[1]
    det = a00 * a11 - a01 * a10
    if abs(det) < 1.0e-12:
        # Not expected for CPC's quarter-conic members, but keep a stable
        # straight-ish fallback for future kernels.
        chord = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
        a = b = chord / 3.0
    else:
        a = (r[0] * a11 - a01 * r[1]) / det
        b = (a00 * r[1] - r[0] * a10) / det
        a = max(0.0, a)
        b = max(0.0, b)

    h0 = _add(p0, _mul(t0, a))
    h1 = _sub(p2, _mul(t1, b))
    return CubicSegment(p0, h0, h1, p2)


DEFAULT_ARC_DEPTH_RATIO = (math.sqrt(2.0) - 1.0) * 0.5


def default_arc_depth(chord: float) -> float:
    """Return the sagitta that produces a 90-degree circular segment.

    This is used as a friendly default when a Fullness construction has
    no previously stored Arc Depth value.  Arc Depth itself is independent and
    may describe shallower, deeper, or major circular segments.
    """
    chord = max(abs(float(chord)), 1.0e-6)
    return chord * DEFAULT_ARC_DEPTH_RATIO


def default_torus_arc_depth(chord: float) -> float:
    """Return the sagitta for a true semicircle over ``chord``."""
    chord = max(abs(float(chord)), 1.0e-6)
    return chord * 0.5


def default_arc_depth_for_primitive(primitive_id: str, chord: float) -> float:
    """Return the semantic Arc Depth default for a CPC primitive.

    Ovolo/Cavetto start as a 90-degree segment.  Half Round/Torus starts as
    an exact semicircle.  Other primitives currently use the quarter-segment
    fallback only as inactive stored state.
    """
    if str(primitive_id).upper() == "TORUS":
        return default_torus_arc_depth(chord)
    return default_arc_depth(chord)


def arc_radius_from_chord_depth(chord: float, depth: float) -> float:
    """Return circle radius from chord length and sagitta/depth.

    r = h/2 + c^2/(8h)

    ``depth`` is a positive magnitude.  Values above chord/2 intentionally
    describe the corresponding major arc; CPC does not silently clamp them to
    a semicircle.
    """
    chord = max(abs(float(chord)), 1.0e-6)
    depth = max(abs(float(depth)), 1.0e-6)
    return depth * 0.5 + (chord * chord) / (8.0 * depth)


def circular_segments_from_chord_depth(
    chord: float,
    depth: float,
    *,
    bulge_sign: float = 1.0,
) -> Tuple[Tuple[CubicSegment, ...], float, float]:
    """Construct a circular segment from chord + sagitta.

    The chord runs from (0, 0) to (chord, 0). ``bulge_sign`` chooses which
    side of the chord contains the arc (+Y or -Y).  The returned central angle
    is always positive and can approach 2*pi for very deep major arcs.

    The circle is represented by standard analytic cubic Bezier arc spans of
    at most 90 degrees, matching CPC's existing circular construction policy.
    """
    chord = max(abs(float(chord)), 1.0e-6)
    depth = max(abs(float(depth)), 1.0e-6)
    sign = 1.0 if float(bulge_sign) >= 0.0 else -1.0

    radius = arc_radius_from_chord_depth(chord, depth)
    # theta = 4 atan(2h/c) naturally selects the minor arc for h<c/2,
    # a semicircle at h=c/2, and the major arc for h>c/2.
    central_angle = 4.0 * math.atan2(2.0 * depth, chord)
    center = (chord * 0.5, sign * (depth - radius))

    start_angle = math.atan2(-center[1], -chord * 0.5)
    signed_sweep = -central_angle if sign > 0.0 else central_angle
    span_count = max(1, int(math.ceil(abs(signed_sweep) / (math.pi * 0.5))))

    segments = []
    for index in range(span_count):
        a0 = start_angle + signed_sweep * (index / span_count)
        a1 = start_angle + signed_sweep * ((index + 1) / span_count)
        segments.append(cubic_ellipse_arc(center, radius, radius, a0, a1))

    return tuple(segments), radius, central_angle


def _effective_quarter_dimensions(width: float, height: float, shape_mode: str) -> Tuple[float, float]:
    width = max(abs(width), 1.0e-6)
    if shape_mode == "CIRCLE":
        return width, width
    return width, max(abs(height), 1.0e-6)


def _normalise_arc_construction_mode(value: str) -> str:
    return "ARC_DEPTH" if str(value).upper() == "ARC_DEPTH" else "FULLNESS"


def make_ovolo(
    width: float,
    height: float,
    shape_mode: str = "CIRCLE",
    fullness: float = 1.0,
    arc_construction_mode: str = "FULLNESS",
    arc_depth: float | None = None,
) -> PrimitiveGeometry:
    mode = _normalise_arc_construction_mode(arc_construction_mode)
    raw_width = max(abs(float(width)), 1.0e-6)
    raw_height = max(abs(float(height)), 1.0e-6)
    fullness = _clamp_fullness(fullness)
    depth = max(abs(float(arc_depth if arc_depth is not None else default_arc_depth(raw_width))), 1.0e-6)

    if mode == "ARC_DEPTH":
        segments, radius, central_angle = circular_segments_from_chord_depth(
            raw_width, depth, bulge_sign=1.0
        )
        return _geometry(
            "OVOLO",
            "Ovolo / Convex Quarter Round",
            segments,
            start_join="HARD",
            end_join="SMOOTH",
            parameters={
                "width": raw_width,
                "height": raw_height,
                "shape_mode": shape_mode,
                "fullness": fullness,
                "arc_construction_mode": mode,
                "arc_depth": depth,
                "radius": radius,
                "central_angle": central_angle,
            },
            construction="CIRCULAR_SEGMENT_ARC_DEPTH",
        )

    width, height = _effective_quarter_dimensions(raw_width, raw_height, shape_mode)
    # P1 is the intersection of the horizontal start tangent and vertical end
    # tangent.  Fullness changes the rational conic weight evenly.
    segment = conic_cubic((0.0, 0.0), (width, 0.0), (width, height), fullness)
    return _geometry(
        "OVOLO",
        "Ovolo / Convex Quarter Round",
        [segment],
        start_join="HARD",
        end_join="SMOOTH",
        parameters={
            "width": width, "height": height, "shape_mode": shape_mode, "fullness": fullness,
            "arc_construction_mode": mode, "arc_depth": depth,
        },
        construction=("CIRCULAR_ARC" if shape_mode == "CIRCLE" else "ELLIPTICAL_ARC")
        if abs(fullness - 1.0) < 1.0e-9 else "CONIC_FULLNESS_ARC",
    )


def make_cavetto(
    width: float,
    height: float,
    shape_mode: str = "CIRCLE",
    fullness: float = 1.0,
    arc_construction_mode: str = "FULLNESS",
    arc_depth: float | None = None,
) -> PrimitiveGeometry:
    mode = _normalise_arc_construction_mode(arc_construction_mode)
    raw_width = max(abs(float(width)), 1.0e-6)
    raw_height = max(abs(float(height)), 1.0e-6)
    fullness = _clamp_fullness(fullness)
    depth = max(abs(float(arc_depth if arc_depth is not None else default_arc_depth(raw_width))), 1.0e-6)

    if mode == "ARC_DEPTH":
        segments, radius, central_angle = circular_segments_from_chord_depth(
            raw_width, depth, bulge_sign=-1.0
        )
        return _geometry(
            "CAVETTO",
            "Cavetto / Concave Cove",
            segments,
            start_join="SMOOTH",
            end_join="HARD",
            parameters={
                "width": raw_width,
                "height": raw_height,
                "shape_mode": shape_mode,
                "fullness": fullness,
                "arc_construction_mode": mode,
                "arc_depth": depth,
                "radius": radius,
                "central_angle": central_angle,
            },
            construction="CIRCULAR_SEGMENT_ARC_DEPTH",
        )

    width, height = _effective_quarter_dimensions(raw_width, raw_height, shape_mode)
    # Opposite tangent intersection produces the concave quarter-conic.
    segment = conic_cubic((0.0, 0.0), (0.0, height), (width, height), fullness)
    return _geometry(
        "CAVETTO",
        "Cavetto / Concave Cove",
        [segment],
        start_join="SMOOTH",
        end_join="HARD",
        parameters={
            "width": width, "height": height, "shape_mode": shape_mode, "fullness": fullness,
            "arc_construction_mode": mode, "arc_depth": depth,
        },
        construction=("CIRCULAR_ARC" if shape_mode == "CIRCLE" else "ELLIPTICAL_ARC")
        if abs(fullness - 1.0) < 1.0e-9 else "CONIC_FULLNESS_ARC",
    )


def make_torus(
    width: float,
    height: float,
    shape_mode: str = "CIRCLE",
    fullness: float = 1.0,
    arc_construction_mode: str = "FULLNESS",
    arc_depth: float | None = None,
) -> PrimitiveGeometry:
    """Half Round / Torus with Fullness or exact chord+sagitta construction.

    Arc Depth uses the same true-circle kernel as Ovolo/Cavetto.  The semantic
    default is ``depth = chord / 2`` so a new Torus is an exact semicircle.
    Shallower/deeper values intentionally become other convex circular
    segments while retaining the Torus architectural role.
    """
    mode = _normalise_arc_construction_mode(arc_construction_mode)
    raw_width = max(abs(float(width)), 1.0e-6)
    raw_height = max(abs(float(height)), 1.0e-6)
    fullness = _clamp_fullness(fullness)
    depth = max(
        abs(float(arc_depth if arc_depth is not None else default_torus_arc_depth(raw_width))),
        1.0e-6,
    )

    if mode == "ARC_DEPTH":
        segments, radius, central_angle = circular_segments_from_chord_depth(
            raw_width, depth, bulge_sign=1.0
        )
        return _geometry(
            "TORUS",
            "Half Round / Torus",
            segments,
            start_join="HARD",
            end_join="HARD",
            parameters={
                "width": raw_width,
                "height": raw_height,
                "shape_mode": shape_mode,
                "fullness": fullness,
                "arc_construction_mode": mode,
                "arc_depth": depth,
                "radius": radius,
                "central_angle": central_angle,
            },
            construction="CIRCULAR_SEGMENT_ARC_DEPTH",
        )

    width = raw_width
    if shape_mode == "CIRCLE":
        height = width * 0.5
    else:
        height = raw_height
    rx = width * 0.5
    crown = (rx, height)
    segments = [
        conic_cubic((0.0, 0.0), (0.0, height), crown, fullness),
        conic_cubic(crown, (width, height), (width, 0.0), fullness),
    ]
    return _geometry(
        "TORUS",
        "Half Round / Torus",
        segments,
        start_join="HARD",
        end_join="HARD",
        parameters={
            "width": width,
            "height": height,
            "shape_mode": shape_mode,
            "fullness": fullness,
            "arc_construction_mode": mode,
            "arc_depth": depth,
        },
        construction=("SEMICIRCLE" if shape_mode == "CIRCLE" else "SEMIELLIPSE")
        if abs(fullness - 1.0) < 1.0e-9 else "CONIC_FULLNESS_TORUS",
    )



def make_classical_scotia(
    width: float,
    height: float,
    fullness: float = 1.0,
    concave_fullness: float = 1.0,
    convex_fullness: float = 1.0,
    arc_construction_mode: str = "ARC_DEPTH",
) -> PrimitiveGeometry:
    """Canonical two-radius Classical Scotia.

    ``width`` is the lower run-out/projection beyond the upper endpoint.
    ``height`` is the total vertical height.  Circular mode is composed of two
    exact tangent quarter circles of different radii.  Fullness mode preserves
    the same endpoints and tangent framework but allows independent optical
    shaping of the upper and lower lobes.
    """
    mode = _normalise_arc_construction_mode(arc_construction_mode)
    solution = compound_geometry.solve_classical_scotia(height, width)

    upper_fullness = _clamp_fullness(concave_fullness)
    lower_fullness = _clamp_fullness(convex_fullness)

    if mode == "ARC_DEPTH":
        raw = compound_geometry.classical_scotia_cubics(solution)
        segments = tuple(CubicSegment(seg.p0, seg.h0, seg.h1, seg.p1) for seg in raw)
        construction = "CLASSICAL_SCOTIA_CIRCULAR_G1"
    else:
        r1 = solution.upper_radius
        # Top quarter: +X tangent -> +Y tangent.
        upper = conic_cubic(
            solution.p0,
            (r1, 0.0),
            solution.join,
            upper_fullness,
        )
        # Lower quarter: +Y tangent -> -X tangent.
        lower = conic_cubic(
            solution.join,
            (r1, solution.height),
            solution.p1,
            lower_fullness,
        )
        segments = (upper, lower)
        construction = "CLASSICAL_SCOTIA_FULLNESS_G1"

    return _geometry(
        "CLASSICAL_SCOTIA",
        "Classical Scotia",
        segments,
        start_join="SMOOTH",
        end_join="SMOOTH",
        parameters={
            "width": solution.projection,
            "height": solution.height,
            "shape_mode": "CIRCLE",
            "fullness": fullness,
            "concave_fullness": upper_fullness,
            "convex_fullness": lower_fullness,
            "arc_construction_mode": mode,
            "upper_radius": solution.upper_radius,
            "lower_radius": solution.lower_radius,
            "radius_ratio": solution.radius_ratio,
        },
        construction=construction,
    )


def _clamp_bias(bias: float) -> float:
    return min(0.85, max(0.15, float(bias)))


def _cyma_biarc_geometry(
    primitive_id: str,
    width: float,
    height: float,
    bias: float,
    concave_fullness: float,
    convex_fullness: float,
    arc_depth: float | None,
) -> PrimitiveGeometry:
    """Return a true two-circle G1 Cyma from primary Arc Depth.

    Width/Height plus the fixed endpoint tangents leave one shape degree of
    freedom. CPC exposes that degree as a length-unit primary Arc Depth
    while deriving Bias, the companion depth and both radii.
    """
    width = max(abs(width), 1.0e-6)
    height = max(abs(height), 1.0e-6)
    orientation = "RECTA" if primitive_id == "CYMA_RECTA" else "REVERSA"
    concave_fullness = _clamp_fullness(concave_fullness)
    convex_fullness = _clamp_fullness(convex_fullness)

    if arc_depth is None:
        depth = compound_geometry.cyma_primary_depth(
            width, height, _clamp_bias(bias), orientation=orientation
        )
    else:
        depth = abs(float(arc_depth))

    solution = compound_geometry.solve_cyma_from_primary_depth(
        width, height, depth, orientation=orientation
    )
    actual_depth = solution.first.sagitta
    cubics = compound_geometry.biarc_cubics(solution)
    segments = [CubicSegment(c.p0, c.h0, c.h1, c.p1) for c in cubics]
    display_name = "Cyma Recta / Ogee" if primitive_id == "CYMA_RECTA" else "Cyma Reversa / Reverse Ogee"

    return _geometry(
        primitive_id,
        display_name,
        segments,
        start_join="HARD",
        end_join="HARD",
        parameters={
            "width": width,
            "height": height,
            "bias": solution.bias,
            "arc_construction_mode": "ARC_DEPTH",
            "arc_depth": actual_depth,
            "primary_arc_depth": actual_depth,
            "secondary_arc_depth": solution.second.sagitta,
            "primary_radius": solution.first.radius,
            "secondary_radius": solution.second.radius,
            "g1_error": solution.g1_error,
            # Preserve inactive alternate-mode settings through Commit/Reopen.
            "concave_fullness": concave_fullness,
            "convex_fullness": convex_fullness,
            "construction_mode": "CIRCULAR_BIARC",
        },
        construction="CIRCULAR_BIARC_G1",
    )


def make_cyma_recta(
    width: float,
    height: float,
    bias: float = 0.5,
    concave_fullness: float = 1.0,
    convex_fullness: float = 1.0,
    arc_construction_mode: str = "FULLNESS",
    arc_depth: float | None = None,
) -> PrimitiveGeometry:
    """Cyma Recta with validated Fullness or true circular biarc construction."""
    mode = _normalise_arc_construction_mode(arc_construction_mode)
    if mode == "ARC_DEPTH":
        return _cyma_biarc_geometry(
            "CYMA_RECTA", width, height, bias, concave_fullness, convex_fullness, arc_depth
        )

    width = max(abs(width), 1.0e-6)
    height = max(abs(height), 1.0e-6)
    bias = _clamp_bias(bias)
    jx = width * bias
    jy = height * bias
    concave_fullness = _clamp_fullness(concave_fullness)
    convex_fullness = _clamp_fullness(convex_fullness)
    join = (jx, jy)

    # Preserve the established Fullness construction:
    # lower lobe horizontal -> vertical; upper lobe vertical -> horizontal.
    first = conic_cubic((0.0, 0.0), (jx, 0.0), join, convex_fullness)
    second = conic_cubic(join, (jx, height), (width, height), concave_fullness)
    return _geometry(
        "CYMA_RECTA",
        "Cyma Recta / Ogee",
        [first, second],
        start_join="HARD",
        end_join="HARD",
        parameters={
            "width": width,
            "height": height,
            "bias": bias,
            "arc_construction_mode": "FULLNESS",
            "construction_mode": "COMPASS"
            if abs(concave_fullness - 1.0) < 1.0e-9 and abs(convex_fullness - 1.0) < 1.0e-9
            else "CONIC_FULLNESS",
            "concave_fullness": concave_fullness,
            "convex_fullness": convex_fullness,
        },
        construction="TWO_ARC_S_G1"
        if abs(concave_fullness - 1.0) < 1.0e-9 and abs(convex_fullness - 1.0) < 1.0e-9
        else "TWO_CONIC_S_G1",
    )


def make_cyma_reversa(
    width: float,
    height: float,
    bias: float = 0.5,
    concave_fullness: float = 1.0,
    convex_fullness: float = 1.0,
    arc_construction_mode: str = "FULLNESS",
    arc_depth: float | None = None,
) -> PrimitiveGeometry:
    """Cyma Reversa with validated Fullness or true circular biarc construction."""
    mode = _normalise_arc_construction_mode(arc_construction_mode)
    if mode == "ARC_DEPTH":
        return _cyma_biarc_geometry(
            "CYMA_REVERSA", width, height, bias, concave_fullness, convex_fullness, arc_depth
        )

    width = max(abs(width), 1.0e-6)
    height = max(abs(height), 1.0e-6)
    bias = _clamp_bias(bias)
    jx = width * bias
    jy = height * bias
    concave_fullness = _clamp_fullness(concave_fullness)
    convex_fullness = _clamp_fullness(convex_fullness)
    join = (jx, jy)

    first = conic_cubic((0.0, 0.0), (0.0, jy), join, concave_fullness)
    second = conic_cubic(join, (width, jy), (width, height), convex_fullness)
    return _geometry(
        "CYMA_REVERSA",
        "Cyma Reversa / Reverse Ogee",
        [first, second],
        start_join="HARD",
        end_join="HARD",
        parameters={
            "width": width,
            "height": height,
            "bias": bias,
            "arc_construction_mode": "FULLNESS",
            "construction_mode": "COMPASS"
            if abs(concave_fullness - 1.0) < 1.0e-9 and abs(convex_fullness - 1.0) < 1.0e-9
            else "CONIC_FULLNESS",
            "concave_fullness": concave_fullness,
            "convex_fullness": convex_fullness,
        },
        construction="TWO_ARC_S_G1"
        if abs(concave_fullness - 1.0) < 1.0e-9 and abs(convex_fullness - 1.0) < 1.0e-9
        else "TWO_CONIC_S_G1",
    )


PRIMITIVE_LABELS = {
    "LINE": "Line / Fascia",
    "OVOLO": "Ovolo / Convex Quarter Round",
    "CAVETTO": "Cavetto / Concave Cove",
    "TORUS": "Half Round / Torus",
    "CYMA_RECTA": "Cyma Recta / Ogee",
    "CYMA_REVERSA": "Cyma Reversa / Reverse Ogee",
}


def generate(
    primitive_id: str,
    *,
    width: float,
    height: float,
    shape_mode: str = "CIRCLE",
    bias: float = 0.5,
    fullness: float = 1.0,
    concave_fullness: float = 1.0,
    convex_fullness: float = 1.0,
    arc_construction_mode: str = "FULLNESS",
    arc_depth: float | None = None,
) -> PrimitiveGeometry:
    if primitive_id == "LINE":
        return make_line(width)
    if primitive_id == "OVOLO":
        return make_ovolo(width, height, shape_mode, fullness, arc_construction_mode, arc_depth)
    if primitive_id == "CAVETTO":
        return make_cavetto(width, height, shape_mode, fullness, arc_construction_mode, arc_depth)
    if primitive_id == "TORUS":
        return make_torus(width, height, shape_mode, fullness, arc_construction_mode, arc_depth)
    if primitive_id == "CYMA_RECTA":
        return make_cyma_recta(
            width, height, bias, concave_fullness, convex_fullness,
            arc_construction_mode, arc_depth,
        )
    if primitive_id == "CYMA_REVERSA":
        return make_cyma_reversa(
            width, height, bias, concave_fullness, convex_fullness,
            arc_construction_mode, arc_depth,
        )
    if primitive_id == "CLASSICAL_SCOTIA":
        return make_classical_scotia(
            width, height, fullness, concave_fullness, convex_fullness,
            arc_construction_mode,
        )
    raise ValueError(f"Unknown CPC primitive: {primitive_id}")
