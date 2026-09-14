"""Unit formatting and safe typed-length parsing for CPC viewport interaction.

The module keeps Architectural Imperial parsing deliberately small and data-only.
It never evaluates Python expressions.  Blender-native unit parsing remains the
preferred path for Scene Units when a Blender context is available.
"""

from __future__ import annotations

import math
import re


_METRIC_RE = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mm|cm|m)?\s*$", re.I)


def _gcd_fraction(numerator: int, denominator: int) -> tuple[int, int]:
    if numerator == 0:
        return 0, 1
    g = math.gcd(abs(int(numerator)), abs(int(denominator)))
    return int(numerator // g), int(denominator // g)


def _mixed_number(value: float, denominator: int) -> tuple[int, int, int]:
    """Return whole, numerator, denominator for a positive value."""
    denominator = max(1, int(denominator))
    total = int(round(float(value) * denominator))
    whole, numerator = divmod(total, denominator)
    if numerator:
        numerator, reduced_den = _gcd_fraction(numerator, denominator)
    else:
        reduced_den = 1
    return whole, numerator, reduced_den


def format_metric(value_m: float) -> str:
    """Compact architecture-oriented metric display.

    Millimetres remain the default below one metre because profile dimensions
    are normally read that way; metre-scale values remain concise.
    """
    value_m = float(value_m)
    av = abs(value_m)
    if av < 1.0:
        return f"{value_m * 1000.0:.2f} mm"
    return f"{value_m:.4f} m"


def format_architectural(value_m: float, denominator: int = 16) -> str:
    denominator = max(1, int(denominator))
    sign = "-" if value_m < 0 else ""
    total_inches = abs(float(value_m)) / 0.0254

    # Round once to the chosen display precision before splitting feet/inches.
    ticks = int(round(total_inches * denominator))
    inches_total = ticks / denominator
    feet = int(inches_total // 12.0)
    inches = inches_total - feet * 12.0

    whole, numerator, reduced_den = _mixed_number(inches, denominator)
    if whole >= 12:
        feet += whole // 12
        whole %= 12

    if numerator:
        inch_text = f"{whole} {numerator}/{reduced_den}" if whole else f"{numerator}/{reduced_den}"
    else:
        inch_text = f"{whole}"

    if feet:
        if whole or numerator:
            return f"{sign}{feet}'-{inch_text}\""
        return f"{sign}{feet}'"
    return f"{sign}{inch_text}\""


def _parse_fraction_token(token: str) -> float:
    token = str(token or "").strip()
    if not token:
        return 0.0
    if "/" in token:
        parts = token.split("/", 1)
        if len(parts) != 2:
            raise ValueError("Invalid fraction")
        num = float(parts[0].strip())
        den = float(parts[1].strip())
        if abs(den) < 1.0e-12:
            raise ValueError("Fraction denominator cannot be zero")
        return num / den
    return float(token)


def _parse_mixed_number(text: str) -> float:
    """Parse decimal, fraction, or mixed-number text without evaluation."""
    s = str(text or "").strip()
    if not s:
        return 0.0

    # Common drafting form: 1-1/2.  Only treat the hyphen as a mixed-number
    # separator when it is internal, not a leading sign.
    if "-" in s[1:] and "/" in s:
        head, tail = s.split("-", 1)
        if head.strip() and tail.strip():
            return float(head.strip()) + _parse_fraction_token(tail.strip())

    tokens = s.split()
    if len(tokens) == 1:
        return _parse_fraction_token(tokens[0])
    if len(tokens) == 2 and "/" in tokens[1]:
        return float(tokens[0]) + _parse_fraction_token(tokens[1])
    raise ValueError(f"Could not parse mixed number: {text}")


def parse_metric(text: str, *, default_unit: str = "mm") -> float:
    match = _METRIC_RE.match(str(text or ""))
    if not match:
        raise ValueError("Enter a metric length such as 25mm, 2.5cm or 0.5m")
    value = float(match.group(1))
    unit = (match.group(2) or default_unit or "mm").lower()
    if unit == "mm":
        return value / 1000.0
    if unit == "cm":
        return value / 100.0
    if unit == "m":
        return value
    raise ValueError("Unsupported metric unit")


def parse_architectural(text: str, *, default_inches: bool = True) -> float:
    """Parse feet/inches/fractions to metres.

    Accepted examples include 3/4\", 1 1/2\", 1' 6\", 1'-6 1/2\", and 2'.
    A unitless value is interpreted as inches when ``default_inches`` is true.
    """
    s = str(text or "").strip()
    if not s:
        raise ValueError("Enter a length")

    # Normalize common Unicode drafting punctuation.
    s = (
        s.replace("’", "'")
         .replace("′", "'")
         .replace("“", '"')
         .replace("”", '"')
         .replace("″", '"')
    )

    # Metric suffixes remain welcome even while Architectural display is active.
    if re.search(r"(?:mm|cm|m)\s*$", s, re.I):
        return parse_metric(s)

    sign = -1.0 if s.startswith("-") else 1.0
    if s[:1] in "+-":
        s = s[1:].strip()

    feet = 0.0
    inches_text = ""
    if "'" in s:
        feet_text, inches_text = s.split("'", 1)
        feet_text = feet_text.strip()
        feet = float(feet_text) if feet_text else 0.0
        inches_text = inches_text.strip()
        if inches_text.startswith("-"):
            inches_text = inches_text[1:].strip()
    else:
        inches_text = s

    if inches_text.endswith('"'):
        inches_text = inches_text[:-1].strip()
    elif "'" not in s and not default_inches:
        raise ValueError("Add an inch or foot unit")

    inches = _parse_mixed_number(inches_text) if inches_text else 0.0
    total_inches = feet * 12.0 + inches
    return sign * total_inches * 0.0254


def format_length(context, value_m: float) -> str:
    settings = getattr(getattr(context, "scene", None), "cpc_settings", None)
    mode = str(getattr(settings, "viewport_unit_mode", "SCENE")) if settings else "SCENE"
    denominator = int(getattr(settings, "imperial_fraction_denominator", "16")) if settings else 16

    if mode == "METRIC":
        return format_metric(value_m)
    if mode == "ARCH":
        return format_architectural(value_m, denominator)

    try:
        import bpy
        unit_settings = context.scene.unit_settings
        system = str(unit_settings.system or "NONE")
        if system != "NONE":
            text = bpy.utils.units.to_string(
                system,
                'LENGTH',
                float(value_m),
                precision=4,
                split_unit=True,
            )
            if text:
                return text
    except Exception:
        pass
    return format_metric(value_m)


def parse_length(context, text: str, *, reference_value: float = 0.0) -> float:
    settings = getattr(getattr(context, "scene", None), "cpc_settings", None)
    mode = str(getattr(settings, "viewport_unit_mode", "SCENE")) if settings else "SCENE"
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Enter a length")

    if mode == "METRIC":
        return parse_metric(raw, default_unit="mm")
    if mode == "ARCH":
        return parse_architectural(raw, default_inches=True)

    # In Scene mode, Blender's parser knows the active scene unit system and
    # accepts its native unit expressions.  A formatted reference supplies the
    # default unit when the typed string is unitless.
    try:
        import bpy
        unit_settings = context.scene.unit_settings
        system = str(unit_settings.system or "NONE")
        if system != "NONE":
            reference = bpy.utils.units.to_string(
                system,
                'LENGTH',
                float(reference_value),
                precision=4,
                split_unit=False,
            )
            return float(
                bpy.utils.units.to_value(
                    system,
                    'LENGTH',
                    raw,
                    str_ref_unit=reference or None,
                )
            )
    except Exception:
        pass

    # With Scene Units disabled, explicit metric/imperial strings remain useful.
    if re.search(r"(?:mm|cm|m)\s*$", raw, re.I):
        return parse_metric(raw)
    if "'" in raw or '"' in raw or "/" in raw:
        return parse_architectural(raw)
    return float(raw)
