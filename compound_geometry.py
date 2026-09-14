"""Pure G1 biarc / compound-circle geometry for Curve Profile Creator.

This module deliberately has no Blender dependency. It provides the
mathematical foundation for true circular Cyma construction and later compound
architectural mouldings such as Classical Scotia.

A biarc connects two endpoints using two genuine circular arcs.  The arcs meet
at one join point and share the same tangent there (G1 continuity).
"""

from dataclasses import dataclass
import math
from typing import Tuple

Point2 = Tuple[float, float]

_EPS = 1.0e-12


class BiarcError(ValueError):
    """Raised when the requested endpoint/tangent configuration is degenerate."""


@dataclass(frozen=True)
class CubicSegment:
    """A cubic Bezier representation span used only as an evaluated output."""

    p0: Point2
    h0: Point2
    h1: Point2
    p1: Point2


@dataclass(frozen=True)
class CircularArc:
    """Analytic circular arc with tangent-aware orientation."""

    p0: Point2
    p1: Point2
    center: Point2
    radius: float
    signed_radius: float
    sweep_angle: float
    start_tangent: Point2
    end_tangent: Point2

    @property
    def chord(self) -> float:
        return _length(_sub(self.p1, self.p0))

    @property
    def sagitta(self) -> float:
        """Positive arc depth from chord to arc at the angular midpoint."""
        return self.radius * (1.0 - math.cos(abs(self.sweep_angle) * 0.5))


@dataclass(frozen=True)
class BiarcSolution:
    """Two circular arcs joined with a common tangent."""

    p0: Point2
    p1: Point2
    start_tangent: Point2
    end_tangent: Point2
    join: Point2
    join_tangent: Point2
    first: CircularArc
    second: CircularArc
    bias: float
    first_tangent_distance: float
    second_tangent_distance: float
    g1_error: float


@dataclass(frozen=True)
class ClassicalScotiaSolution:
    """Canonical two-quadrant scotia with different radii.

    ``projection`` is the lower run-out beyond the upper endpoint.  ``height``
    is the total vertical rise.  The construction derives two positive radii:

        upper_radius = (height - projection) / 2
        lower_radius = (height + projection) / 2

    Both arcs are exact quarter circles, their centres lie on the same
    horizontal line, and they meet at one common tangent.
    """

    height: float
    projection: float
    upper_radius: float
    lower_radius: float
    radius_ratio: float
    p0: Point2
    join: Point2
    p1: Point2
    upper: CircularArc
    lower: CircularArc
    g1_error: float


# ---------------------------------------------------------------------------
# Small vector kernel
# ---------------------------------------------------------------------------


def _add(a: Point2, b: Point2) -> Point2:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Point2, b: Point2) -> Point2:
    return (a[0] - b[0], a[1] - b[1])


def _mul(a: Point2, scalar: float) -> Point2:
    return (a[0] * scalar, a[1] * scalar)


def _dot(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Point2, b: Point2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _length(v: Point2) -> float:
    return math.hypot(v[0], v[1])


def _normalise(v: Point2) -> Point2:
    length = _length(v)
    if length < _EPS:
        raise BiarcError("Biarc tangent vectors must be non-zero")
    return (v[0] / length, v[1] / length)


def _left_normal(v: Point2) -> Point2:
    return (-v[1], v[0])


def _distance(a: Point2, b: Point2) -> float:
    return _length(_sub(a, b))


def _clamp_bias(bias: float) -> float:
    # CPC's existing Cyma public range is 0.15..0.85.  Keeping the same range
    # avoids near-zero lobes and gives the future Blender integration identical
    # endpoint semantics.
    return min(0.85, max(0.15, float(bias)))


# ---------------------------------------------------------------------------
# Circular-arc construction
# ---------------------------------------------------------------------------


def _oriented_sweep(center: Point2, p0: Point2, p1: Point2, signed_radius: float) -> float:
    r0 = _sub(p0, center)
    r1 = _sub(p1, center)
    raw = math.atan2(_cross(r0, r1), _dot(r0, r1))

    if signed_radius > 0.0:
        if raw <= 0.0:
            raw += math.tau
    else:
        if raw >= 0.0:
            raw -= math.tau

    # A valid CPC biarc lobe should never need a full revolution.  Treat a
    # numerically collapsed or looping solution as invalid rather than hiding it.
    if abs(raw) < 1.0e-10 or abs(raw) >= math.tau - 1.0e-8:
        raise BiarcError("Degenerate circular-arc sweep")
    return raw


def _tangent_on_circle(center: Point2, point: Point2, sweep_sign: float) -> Point2:
    radial = _normalise(_sub(point, center))
    tangent = _left_normal(radial)
    if sweep_sign < 0.0:
        tangent = _mul(tangent, -1.0)
    return _normalise(tangent)


def _arc_from_start_tangent(p0: Point2, tangent: Point2, p1: Point2) -> CircularArc:
    """Construct the circle through p0/p1 whose tangent at p0 is ``tangent``."""
    tangent = _normalise(tangent)
    chord = _sub(p1, p0)
    normal = _left_normal(tangent)
    denominator = 2.0 * _dot(normal, chord)
    if abs(denominator) < _EPS:
        raise BiarcError("Circular arc is degenerate/straight at the start endpoint")

    signed_radius = _dot(chord, chord) / denominator
    center = _add(p0, _mul(normal, signed_radius))
    radius = abs(signed_radius)
    sweep = _oriented_sweep(center, p0, p1, signed_radius)
    end_tangent = _tangent_on_circle(center, p1, sweep)
    return CircularArc(
        p0=p0,
        p1=p1,
        center=center,
        radius=radius,
        signed_radius=signed_radius,
        sweep_angle=sweep,
        start_tangent=tangent,
        end_tangent=end_tangent,
    )


def _arc_from_end_tangent(p0: Point2, p1: Point2, tangent: Point2) -> CircularArc:
    """Construct the circle through p0/p1 whose tangent at p1 is ``tangent``."""
    tangent = _normalise(tangent)
    chord_from_end = _sub(p0, p1)
    normal = _left_normal(tangent)
    denominator = 2.0 * _dot(normal, chord_from_end)
    if abs(denominator) < _EPS:
        raise BiarcError("Circular arc is degenerate/straight at the end endpoint")

    signed_radius = _dot(chord_from_end, chord_from_end) / denominator
    center = _add(p1, _mul(normal, signed_radius))
    radius = abs(signed_radius)
    sweep = _oriented_sweep(center, p0, p1, signed_radius)
    start_tangent = _tangent_on_circle(center, p0, sweep)
    return CircularArc(
        p0=p0,
        p1=p1,
        center=center,
        radius=radius,
        signed_radius=signed_radius,
        sweep_angle=sweep,
        start_tangent=start_tangent,
        end_tangent=tangent,
    )


# ---------------------------------------------------------------------------
# Generic G1 biarc solver
# ---------------------------------------------------------------------------


def solve_biarc(
    p0: Point2,
    start_tangent: Point2,
    p1: Point2,
    end_tangent: Point2,
    *,
    bias: float = 0.5,
) -> BiarcSolution:
    """Solve a two-circle G1 biarc between endpoints and endpoint tangents.

    ``bias`` controls the ratio of the two tangent-distance parameters.  For
    CPC Cyma, where start/end tangents are parallel and equal, this has a very
    useful architectural interpretation: the biarc join lies exactly at
    ``p0 + bias * (p1-p0)``.  This preserves the existing Cyma Bias concept.

    The construction follows the tangent-intersection form of a biarc.  If
    ``d0`` and ``d1`` are distances from each endpoint to its lobe's tangent
    intersection, the two tangent intersections and the common join are
    collinear.  The quadratic below enforces that geometry exactly.
    """
    t0 = _normalise(start_tangent)
    t1 = _normalise(end_tangent)
    chord = _sub(p1, p0)
    chord_sq = _dot(chord, chord)
    if chord_sq < _EPS:
        raise BiarcError("Biarc endpoints must be distinct")

    b = _clamp_bias(bias)
    # d1 = beta * d0.  This mapping makes equal endpoint tangents place the
    # join at exactly ``bias`` along the endpoint chord.
    beta = (1.0 - b) / b

    a_q = 2.0 * beta * (_dot(t0, t1) - 1.0)
    b_q = -2.0 * _dot(chord, _add(t0, _mul(t1, beta)))
    c_q = chord_sq

    roots = []
    if abs(a_q) < _EPS:
        if abs(b_q) < _EPS:
            raise BiarcError("Biarc tangent configuration has no finite solution")
        roots.append(-c_q / b_q)
    else:
        discriminant = b_q * b_q - 4.0 * a_q * c_q
        if discriminant < -1.0e-10:
            raise BiarcError("Biarc tangent configuration has no real solution")
        root_disc = math.sqrt(max(0.0, discriminant))
        roots.extend((
            (-b_q + root_disc) / (2.0 * a_q),
            (-b_q - root_disc) / (2.0 * a_q),
        ))

    positive = [value for value in roots if math.isfinite(value) and value > 1.0e-10]
    if not positive:
        raise BiarcError("Biarc tangent configuration has no positive tangent-distance solution")

    # For ordinary forward-facing architectural configurations there is one
    # positive root.  If a future generalized case yields more, prefer the
    # shorter non-looping construction.
    d0 = min(positive)
    d1 = beta * d0

    q0 = _add(p0, _mul(t0, d0))
    q1 = _sub(p1, _mul(t1, d1))
    join = _mul(_add(_mul(q0, d1), _mul(q1, d0)), 1.0 / (d0 + d1))

    first = _arc_from_start_tangent(p0, t0, join)
    second = _arc_from_end_tangent(join, p1, t1)

    jt0 = first.end_tangent
    jt1 = second.start_tangent
    join_tangent = _normalise(_add(jt0, jt1))
    g1_error = max(
        _distance(first.p1, second.p0),
        _length(_sub(jt0, jt1)),
    )
    if g1_error > 1.0e-7:
        raise BiarcError(f"Biarc failed G1 continuity check ({g1_error:.3e})")

    return BiarcSolution(
        p0=p0,
        p1=p1,
        start_tangent=t0,
        end_tangent=t1,
        join=join,
        join_tangent=join_tangent,
        first=first,
        second=second,
        bias=b,
        first_tangent_distance=d0,
        second_tangent_distance=d1,
        g1_error=g1_error,
    )


# ---------------------------------------------------------------------------
# Classical Scotia
# ---------------------------------------------------------------------------


def solve_classical_scotia(height: float, projection: float) -> ClassicalScotiaSolution:
    """Solve CPC's canonical two-radius Classical Scotia.

    Historical compass constructions commonly describe the scotia as two
    tangent quarter circles of unequal radius, with the lower portion
    projecting beyond the upper and the two circle centres lying on one
    horizontal line.

    CPC exposes those architectural quantities directly:

    ``height``
        Total vertical distance from upper endpoint to lower endpoint.

    ``projection``
        Horizontal run-out of the lower endpoint beyond the upper endpoint.

    Valid geometry requires ``0 < projection < height``.  The two quarter
    circle radii are then uniquely determined.
    """
    height = max(abs(float(height)), 1.0e-6)
    projection = max(abs(float(projection)), 1.0e-6)
    # Keep both radii positive and avoid a numerically collapsed upper arc.
    projection = min(projection, height * 0.95)

    upper_radius = 0.5 * (height - projection)
    lower_radius = 0.5 * (height + projection)
    ratio = lower_radius / upper_radius

    p0 = (0.0, 0.0)
    join = (upper_radius, upper_radius)
    p1 = (-projection, height)

    upper_center = (0.0, upper_radius)
    lower_center = (-projection, upper_radius)

    upper = CircularArc(
        p0=p0,
        p1=join,
        center=upper_center,
        radius=upper_radius,
        signed_radius=upper_radius,
        sweep_angle=math.pi * 0.5,
        start_tangent=(1.0, 0.0),
        end_tangent=(0.0, 1.0),
    )
    lower = CircularArc(
        p0=join,
        p1=p1,
        center=lower_center,
        radius=lower_radius,
        signed_radius=lower_radius,
        sweep_angle=math.pi * 0.5,
        start_tangent=(0.0, 1.0),
        end_tangent=(-1.0, 0.0),
    )

    g1_error = max(
        _distance(upper.p1, lower.p0),
        _length(_sub(upper.end_tangent, lower.start_tangent)),
    )
    if g1_error > 1.0e-10:
        raise BiarcError(f"Classical Scotia failed G1 continuity check ({g1_error:.3e})")

    return ClassicalScotiaSolution(
        height=height,
        projection=projection,
        upper_radius=upper_radius,
        lower_radius=lower_radius,
        radius_ratio=ratio,
        p0=p0,
        join=join,
        p1=p1,
        upper=upper,
        lower=lower,
        g1_error=g1_error,
    )


def classical_scotia_cubics(solution: ClassicalScotiaSolution) -> Tuple[CubicSegment, ...]:
    """Return the two exact quarter circles as evaluated cubic spans."""
    return circular_arc_cubics(solution.upper) + circular_arc_cubics(solution.lower)


# ---------------------------------------------------------------------------
# CPC Cyma wrappers and semantic measurements
# ---------------------------------------------------------------------------


def solve_cyma_recta(width: float, height: float, bias: float = 0.5) -> BiarcSolution:
    """True circular Cyma Recta foundation: horizontal endpoint tangents."""
    width = max(abs(float(width)), 1.0e-6)
    height = max(abs(float(height)), 1.0e-6)
    return solve_biarc(
        (0.0, 0.0),
        (1.0, 0.0),
        (width, height),
        (1.0, 0.0),
        bias=bias,
    )


def solve_cyma_reversa(width: float, height: float, bias: float = 0.5) -> BiarcSolution:
    """True circular Cyma Reversa foundation: vertical endpoint tangents."""
    width = max(abs(float(width)), 1.0e-6)
    height = max(abs(float(height)), 1.0e-6)
    return solve_biarc(
        (0.0, 0.0),
        (0.0, 1.0),
        (width, height),
        (0.0, 1.0),
        bias=bias,
    )


def cyma_depth_budget(width: float, height: float, *, orientation: str = "RECTA") -> float:
    """Return the fixed sum of the two Cyma lobe sagittae.

    With fixed endpoints and fixed endpoint tangents, a G1 circular biarc has
    only one free shape parameter.  CPC's Bias consumes that degree of freedom.
    Therefore an additional independent Arc Depth cannot also be free without
    changing another semantic constraint.

    For CPC's parallel-tangent Cyma family the two lobe sagittae partition one
    fixed total depth budget, and Bias is exactly the partition fraction.
    """
    solver = solve_cyma_recta if str(orientation).upper() == "RECTA" else solve_cyma_reversa
    solution = solver(width, height, 0.5)
    return solution.first.sagitta + solution.second.sagitta


def cyma_primary_depth(width: float, height: float, bias: float, *, orientation: str = "RECTA") -> float:
    """Return the first lobe's true circular sagitta for the requested Bias."""
    solver = solve_cyma_recta if str(orientation).upper() == "RECTA" else solve_cyma_reversa
    return solver(width, height, bias).first.sagitta


def cyma_bias_from_primary_depth(
    width: float,
    height: float,
    primary_depth: float,
    *,
    orientation: str = "RECTA",
) -> float:
    """Convert a first-lobe sagitta into CPC's constrained Cyma Bias.

    This bridges the solver to the user-facing ``D`` parameter.
    The value is constrained to CPC's existing 0.15..0.85 Bias range.
    """
    budget = cyma_depth_budget(width, height, orientation=orientation)
    if budget < _EPS:
        raise BiarcError("Cyma depth budget collapsed")
    return _clamp_bias(abs(float(primary_depth)) / budget)


def solve_cyma_from_primary_depth(
    width: float,
    height: float,
    primary_depth: float,
    *,
    orientation: str = "RECTA",
) -> BiarcSolution:
    """Solve CPC Cyma from the public ``D`` / primary-depth value.

    ``D`` does not add another degree of freedom.  It is simply a length-unit
    representation of the existing Bias degree of freedom.  The companion
    lobe depth and both radii remain derived so G1 continuity cannot be broken.
    """
    orientation = str(orientation or "RECTA").upper()
    bias = cyma_bias_from_primary_depth(
        width,
        height,
        primary_depth,
        orientation=orientation,
    )
    solver = solve_cyma_recta if orientation == "RECTA" else solve_cyma_reversa
    return solver(width, height, bias)


# ---------------------------------------------------------------------------
# Analytic circle -> evaluated cubic Bezier conversion
# ---------------------------------------------------------------------------


def _cubic_circle_span(center: Point2, radius: float, start_angle: float, end_angle: float) -> CubicSegment:
    delta = end_angle - start_angle
    if abs(delta) > math.pi / 2.0 + 1.0e-9:
        raise ValueError("Circular cubic spans must be 90 degrees or less")

    cx, cy = center

    def point(theta: float) -> Point2:
        return (cx + radius * math.cos(theta), cy + radius * math.sin(theta))

    def derivative(theta: float) -> Point2:
        return (-radius * math.sin(theta), radius * math.cos(theta))

    p0 = point(start_angle)
    p1 = point(end_angle)
    d0 = derivative(start_angle)
    d1 = derivative(end_angle)
    k = (4.0 / 3.0) * math.tan(delta / 4.0)
    return CubicSegment(
        p0=p0,
        h0=_add(p0, _mul(d0, k)),
        h1=_sub(p1, _mul(d1, k)),
        p1=p1,
    )


def circular_arc_cubics(arc: CircularArc) -> Tuple[CubicSegment, ...]:
    """Convert one analytic circle arc into <=90 degree cubic spans."""
    start = math.atan2(arc.p0[1] - arc.center[1], arc.p0[0] - arc.center[0])
    count = max(1, int(math.ceil(abs(arc.sweep_angle) / (math.pi / 2.0))))
    step = arc.sweep_angle / count
    return tuple(
        _cubic_circle_span(arc.center, arc.radius, start + i * step, start + (i + 1) * step)
        for i in range(count)
    )


def biarc_cubics(solution: BiarcSolution) -> Tuple[CubicSegment, ...]:
    """Return the evaluated cubic representation of both analytic arcs."""
    return circular_arc_cubics(solution.first) + circular_arc_cubics(solution.second)
