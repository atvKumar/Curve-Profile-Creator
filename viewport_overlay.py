"""Transient viewport interaction overlay for Curve Profile Creator.

CPC uses one shared GPU/BLF substrate for placement feedback, semantic
viewport dimensions, hover/active-field state, numeric entry, and snap intent.
Nothing in this module creates persistent Blender scene geometry.
"""

from dataclasses import dataclass, field
import math

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from bpy_extras import view3d_utils

from . import interaction_units, library, viewport_semantics


_HANDLER_3D = None
_HANDLER_2D = None


@dataclass
class ViewportInteractionState:
    active: bool = False
    owner: str = ""
    title: str = ""
    mode: str = ""
    active_field: str = ""
    hover_field: str = ""
    input_text: str = ""
    scrub_active: bool = False
    message: str = ""
    mouse_region: tuple = (0.0, 0.0)
    area_ptr: int = 0
    region_ptr: int = 0
    object_ptr: int = 0
    snap_kind: str = ""
    snap_label: str = ""
    snap_world: tuple | None = None
    anchor_label: str = ""
    lines: list = field(default_factory=list)


_STATE = ViewportInteractionState()
_UNSET = object()
_DIM_HIT_RECTS = {}


# Restrained functional colors distinguish hover/active state without
# turning the viewport into a dense general-CAD overlay.
_COLOR_PRIMARY = (0.95, 0.72, 0.20, 1.0)
_COLOR_SECONDARY = (0.72, 0.82, 0.95, 0.92)
_COLOR_SNAP = (0.30, 0.95, 0.52, 1.0)
_COLOR_TEXT = (0.96, 0.96, 0.96, 1.0)
_COLOR_MUTED = (0.72, 0.75, 0.80, 1.0)
_COLOR_HOVER = (0.45, 0.86, 1.0, 1.0)
_COLOR_ACTIVE = (1.0, 0.80, 0.24, 1.0)
_COLOR_ERROR = (1.0, 0.45, 0.38, 1.0)


def _settings(context):
    scene = getattr(context, "scene", None)
    return getattr(scene, "cpc_settings", None) if scene else None


def enabled(context):
    settings = _settings(context)
    return bool(settings and getattr(settings, "viewport_guides", True))


def format_length(context, value):
    return interaction_units.format_length(context, float(value))


def _view_key(context):
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    try:
        return (int(area.as_pointer()) if area else 0, int(region.as_pointer()) if region else 0)
    except Exception:
        return (0, 0)


def tag_redraw_all(context=None):
    wm = getattr(context, "window_manager", None) if context else getattr(bpy.context, "window_manager", None)
    if not wm:
        return
    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def begin_modal(owner, *, title="", mode="PLACE", mouse_region=(0.0, 0.0), area_ptr=0, region_ptr=0):
    ensure_handlers()
    _STATE.active = True
    _STATE.owner = str(owner or "")
    _STATE.title = str(title or "")
    _STATE.mode = str(mode or "PLACE")
    _STATE.active_field = ""
    _STATE.hover_field = ""
    _STATE.input_text = ""
    _STATE.scrub_active = False
    _STATE.message = ""
    _STATE.mouse_region = tuple(mouse_region)
    _STATE.area_ptr = int(area_ptr or 0)
    _STATE.region_ptr = int(region_ptr or 0)
    _STATE.object_ptr = 0
    _STATE.snap_kind = ""
    _STATE.snap_label = ""
    _STATE.snap_world = None
    _STATE.anchor_label = ""
    _STATE.lines = []
    tag_redraw_all()


def begin_dimension_edit(owner, obj, context, *, mouse_region=(0.0, 0.0), area_ptr=0, region_ptr=0):
    ensure_handlers()
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    _STATE.active = True
    _STATE.owner = str(owner or "")
    _STATE.title = "Viewport Dimension Edit"
    _STATE.mode = "DIMENSION_EDIT"
    _STATE.active_field = ""
    _STATE.hover_field = ""
    _STATE.input_text = ""
    _STATE.scrub_active = False
    _STATE.message = ""
    _STATE.mouse_region = tuple(mouse_region)
    _STATE.area_ptr = int(area_ptr or (area.as_pointer() if area else 0))
    _STATE.region_ptr = int(region_ptr or (region.as_pointer() if region else 0))
    try:
        _STATE.object_ptr = int(obj.as_pointer())
    except Exception:
        _STATE.object_ptr = 0
    _STATE.snap_kind = ""
    _STATE.snap_label = ""
    _STATE.snap_world = None
    _STATE.anchor_label = ""
    _STATE.lines = []
    tag_redraw_all(context)


def update_modal(
    *,
    owner=None,
    title=None,
    mode=None,
    active_field=None,
    hover_field=None,
    input_text=None,
    scrub_active=None,
    message=None,
    mouse_region=None,
    snap_kind=None,
    snap_label=None,
    snap_world=_UNSET,
    anchor_label=None,
    lines=None,
):
    if owner is not None:
        _STATE.owner = str(owner)
    if title is not None:
        _STATE.title = str(title)
    if mode is not None:
        _STATE.mode = str(mode)
    if active_field is not None:
        _STATE.active_field = str(active_field)
    if hover_field is not None:
        _STATE.hover_field = str(hover_field)
    if input_text is not None:
        _STATE.input_text = str(input_text)
    if scrub_active is not None:
        _STATE.scrub_active = bool(scrub_active)
    if message is not None:
        _STATE.message = str(message)
    if mouse_region is not None:
        _STATE.mouse_region = tuple(mouse_region)
    if snap_kind is not None:
        _STATE.snap_kind = str(snap_kind)
    if snap_label is not None:
        _STATE.snap_label = str(snap_label)
    if snap_world is not _UNSET:
        _STATE.snap_world = tuple(snap_world) if snap_world is not None else None
    if anchor_label is not None:
        _STATE.anchor_label = str(anchor_label)
    if lines is not None:
        _STATE.lines = list(lines)
    _STATE.active = True
    tag_redraw_all()


def update_dimension_edit(*, mouse_region=None, hover_field=None, active_field=None, input_text=None, scrub_active=None, message=None):
    update_modal(
        mode="DIMENSION_EDIT",
        mouse_region=mouse_region,
        hover_field=hover_field,
        active_field=active_field,
        input_text=input_text,
        scrub_active=scrub_active,
        message=message,
    )


def clear_modal(owner=None):
    if owner and _STATE.owner and str(owner) != _STATE.owner:
        return
    _STATE.active = False
    _STATE.owner = ""
    _STATE.title = ""
    _STATE.mode = ""
    _STATE.active_field = ""
    _STATE.hover_field = ""
    _STATE.input_text = ""
    _STATE.scrub_active = False
    _STATE.message = ""
    _STATE.area_ptr = 0
    _STATE.region_ptr = 0
    _STATE.object_ptr = 0
    _STATE.snap_kind = ""
    _STATE.snap_label = ""
    _STATE.snap_world = None
    _STATE.anchor_label = ""
    _STATE.lines = []
    _DIM_HIT_RECTS.clear()
    tag_redraw_all()


def _modal_active_here(context):
    if not _STATE.active:
        return False
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    try:
        if _STATE.area_ptr and (not area or int(area.as_pointer()) != _STATE.area_ptr):
            return False
        if _STATE.region_ptr and (not region or int(region.as_pointer()) != _STATE.region_ptr):
            return False
    except Exception:
        return False
    return True


def dimension_edit_active_here(context):
    return _modal_active_here(context) and _STATE.mode == "DIMENSION_EDIT"


def dimension_edit_active():
    return bool(_STATE.active and _STATE.mode == "DIMENSION_EDIT")


def hit_test_dimension(context, x, y, *, area_ptr=0, region_ptr=0):
    key = (int(area_ptr), int(region_ptr)) if area_ptr or region_ptr else _view_key(context)
    rects = _DIM_HIT_RECTS.get(key, {})
    px = float(x)
    py = float(y)
    for field_id, rect in rects.items():
        x0, y0, x1, y1 = rect
        if x0 <= px <= x1 and y0 <= py <= y1:
            return field_id
    return ""


def _selected_cpc_part(context):
    obj = getattr(context, "object", None)
    if not obj or obj.type != 'CURVE':
        return None
    if not obj.get("cpc_part") or not obj.get("cpc_parametric") or obj.get("cpc_preview"):
        return None
    return obj


def _part_title(obj):
    primitive_id = str(obj.get("cpc_primitive_id", ""))
    primitive_name = str(obj.get("cpc_primitive_name", primitive_id or "CPC Part"))
    role = str(obj.get("cpc_role", "") or "").replace('_', ' ').title()
    arch_name = str(obj.get("cpc_arch_component_name", "") or "")
    if arch_name:
        return f"{arch_name} • {role or primitive_name}"
    return primitive_name


def _part_meta_line(obj):
    anchor_index = int(obj.get("cpc_anchor_index", 0))
    rotation = math.degrees(float(getattr(obj, "cpc_part_rotation", 0.0)))
    return f"{'End' if anchor_index else 'Start'} Edit Anchor • Rotation {rotation:.1f}°"


def _draw_points(coords, color, size):
    if not coords:
        return
    shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'POINTS', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    gpu.state.point_size_set(float(size))
    batch.draw(shader)


def _draw_lines(coords, color, width=1.5):
    if not coords:
        return
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": coords})
    shader.bind()
    shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
    shader.uniform_float("lineWidth", float(width))
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_basic_dimension_line(obj, start, end):
    """Draw one restrained true geometric dimension guide where semantics match.

    A straight Line's Length and an Arc-Depth primitive's Chord are exactly the
    endpoint-to-endpoint distance.  Other CPC Width/Height semantics are not
    necessarily the endpoint chord, so we deliberately do not draw a false
    generic dimension line for them.
    """
    if obj.get("cpc_arch_instance_id"):
        return
    primitive_id = str(obj.get("cpc_primitive_id", ""))
    valid = primitive_id == 'LINE'
    if primitive_id in {'OVOLO', 'CAVETTO', 'TORUS'}:
        valid = str(getattr(obj, "cpc_param_arc_construction_mode", "FULLNESS")) == 'ARC_DEPTH'
    if not valid:
        return

    chord = end - start
    span = chord.length
    if span <= 1.0e-8:
        return
    normal = Vector((-chord.y, chord.x, 0.0))
    if normal.length <= 1.0e-8:
        return
    normal.normalize()
    offset = max(span * 0.12, 0.006)
    a = start + normal * offset
    b = end + normal * offset
    _draw_lines([start, a, end, b, a, b], _COLOR_SECONDARY, 1.15)


def _draw_3d():
    context = bpy.context
    if not enabled(context):
        return
    old_blend = gpu.state.blend_get()
    old_depth = gpu.state.depth_test_get()
    try:
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')

        modal_here = _modal_active_here(context)
        selected = _selected_cpc_part(context)
        show_selected = selected and (not modal_here or _STATE.mode == "DIMENSION_EDIT")
        if show_selected:
            start = library.object_endpoint_world(selected, 0)
            end = library.object_endpoint_world(selected, 1)
            anchor_index = int(selected.get("cpc_anchor_index", 0))
            fixed = start if anchor_index == 0 else end
            free = end if anchor_index == 0 else start
            _draw_points([fixed], _COLOR_PRIMARY, 11.0)
            _draw_points([free], _COLOR_SECONDARY, 7.0)

            outward = library.object_endpoint_outward_world(selected, anchor_index)
            span = max((end - start).length, 0.01)
            if outward.length > 1.0e-8:
                outward = outward.normalized()
                length = max(span * 0.28, 0.006)
                _draw_lines([fixed, fixed + outward * length], _COLOR_PRIMARY, 1.7)
            _draw_basic_dimension_line(selected, start, end)

        if modal_here and _STATE.mode != "DIMENSION_EDIT" and _STATE.snap_world is not None:
            snap = Vector(_STATE.snap_world)
            _draw_points([snap], _COLOR_SNAP, 13.0)
    except Exception as exc:
        print(f"[Curve Profile Creator] viewport 3D overlay warning: {exc}")
    finally:
        try:
            gpu.state.depth_test_set(old_depth)
            gpu.state.blend_set(old_blend)
        except Exception:
            pass


def _font_setup(font_id=0, size=13.0):
    try:
        blf.enable(font_id, blf.SHADOW)
        blf.shadow(font_id, 3, 0.0, 0.0, 0.0, 0.75)
        blf.shadow_offset(font_id, 1, -1)
    except Exception:
        pass
    blf.size(font_id, float(size))


def _font_teardown(font_id=0):
    try:
        blf.disable(font_id, blf.SHADOW)
    except Exception:
        pass


def _draw_text_block(x, y, lines, *, primary=True):
    font_id = 0
    size = 13.0
    line_h = 18.0
    _font_setup(font_id, size)
    for index, text in enumerate(lines):
        if not text:
            continue
        color = _COLOR_TEXT if (primary or index == 0) else _COLOR_MUTED
        if index > 0:
            color = _COLOR_MUTED
        blf.color(font_id, *color)
        blf.size(font_id, size if index else size + 1.0)
        blf.position(font_id, float(x), float(y - index * line_h), 0)
        blf.draw(font_id, str(text))
    _font_teardown(font_id)


def _selected_hud_position(context, obj):
    region = getattr(context, "region", None)
    rv3d = getattr(getattr(context, "space_data", None), "region_3d", None)
    if not region or not rv3d:
        return None
    start = library.object_endpoint_world(obj, 0)
    end = library.object_endpoint_world(obj, 1)
    mid = (start + end) * 0.5
    screen = view3d_utils.location_3d_to_region_2d(region, rv3d, mid, default=None)
    if screen is None:
        return None
    return (screen.x + 18.0, screen.y + 58.0)


def _draw_selected_semantic_hud(context, obj, x, y):
    key = _view_key(context)
    _DIM_HIT_RECTS[key] = {}
    edit_active = dimension_edit_active_here(context)
    fields = viewport_semantics.fields_for(obj)

    font_id = 0
    base_size = 13.0
    line_h = 19.0
    _font_setup(font_id, base_size)

    title = _part_title(obj)
    if edit_active:
        title = f"Viewport Edit • {title}"
    lines_before = [title, _part_meta_line(obj)]
    cursor_y = float(y)

    for index, text in enumerate(lines_before):
        blf.size(font_id, base_size + 1.0 if index == 0 else base_size)
        blf.color(font_id, *(_COLOR_TEXT if index == 0 else _COLOR_MUTED))
        blf.position(font_id, float(x), cursor_y, 0)
        blf.draw(font_id, text)
        cursor_y -= line_h

    for field in fields:
        is_active = edit_active and field.field_id == _STATE.active_field
        is_hover = edit_active and field.field_id == _STATE.hover_field and field.editable
        if is_active:
            value_text = format_length(context, field.value) if _STATE.scrub_active else ((_STATE.input_text or "") + "▌")
            color = _COLOR_ACTIVE
        else:
            value_text = format_length(context, field.value)
            color = _COLOR_HOVER if is_hover else (_COLOR_TEXT if field.editable else _COLOR_MUTED)

        prefix = "› " if is_hover or is_active else "  "
        text = f"{prefix}{field.label}  {value_text}"
        blf.size(font_id, base_size)
        blf.color(font_id, *color)
        blf.position(font_id, float(x), cursor_y, 0)
        blf.draw(font_id, text)

        if edit_active and field.editable:
            width, height = blf.dimensions(font_id, text)
            value_prefix = f"{prefix}{field.label}  "
            value_x_offset, _ = blf.dimensions(font_id, value_prefix)
            _DIM_HIT_RECTS[key][field.field_id] = (
                float(x) + float(value_x_offset) - 5.0,
                cursor_y - 4.0,
                float(x) + float(width) + 8.0,
                cursor_y + float(height) + 5.0,
            )
        cursor_y -= line_h

    if edit_active:
        cursor_y -= 2.0
        instruction = "Drag value to scrub • Click to type • L/W/H/D/F • Tab anchor • Esc exit"
        blf.color(font_id, *_COLOR_MUTED)
        blf.position(font_id, float(x), cursor_y, 0)
        blf.draw(font_id, instruction)
        cursor_y -= line_h
        if _STATE.message:
            color = _COLOR_ERROR if _STATE.message.startswith("Error") else _COLOR_MUTED
            blf.color(font_id, *color)
            blf.position(font_id, float(x), cursor_y, 0)
            blf.draw(font_id, _STATE.message)

    _font_teardown(font_id)


def _draw_2d():
    context = bpy.context
    if not enabled(context):
        return
    try:
        modal_here = _modal_active_here(context)
        if modal_here and _STATE.mode != "DIMENSION_EDIT":
            x, y = _STATE.mouse_region
            x += 18.0
            y += 42.0
            lines = []
            if _STATE.title:
                lines.append(_STATE.title)
            mode = _STATE.mode.replace('_', ' ').title() if _STATE.mode else "Place"
            active = _STATE.active_field.replace('_', ' ').title() if _STATE.active_field else ""
            line = mode
            if active and active.lower() != mode.lower():
                line += f" • {active}"
            if _STATE.anchor_label:
                line += f" • {_STATE.anchor_label}"
            lines.append(line)
            lines.extend(_STATE.lines)
            if _STATE.snap_label:
                lines.append(f"Snap • {_STATE.snap_label}")
            _draw_text_block(x, y, lines)
            return

        selected = _selected_cpc_part(context)
        if not selected:
            _DIM_HIT_RECTS.pop(_view_key(context), None)
            return
        pos = _selected_hud_position(context, selected)
        if pos is None:
            _DIM_HIT_RECTS.pop(_view_key(context), None)
            return
        _draw_selected_semantic_hud(context, selected, pos[0], pos[1])
    except Exception as exc:
        print(f"[Curve Profile Creator] viewport 2D overlay warning: {exc}")


def ensure_handlers():
    """Create CPC viewport draw handlers only after user interaction requests them."""
    global _HANDLER_3D, _HANDLER_2D
    if _HANDLER_3D is None:
        _HANDLER_3D = bpy.types.SpaceView3D.draw_handler_add(_draw_3d, (), 'WINDOW', 'POST_VIEW')
    if _HANDLER_2D is None:
        _HANDLER_2D = bpy.types.SpaceView3D.draw_handler_add(_draw_2d, (), 'WINDOW', 'POST_PIXEL')
    tag_redraw_all()


def remove_handlers():
    """Remove CPC viewport draw handlers if they were created."""
    global _HANDLER_3D, _HANDLER_2D
    if _HANDLER_3D is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLER_3D, 'WINDOW')
        except Exception:
            pass
        _HANDLER_3D = None
    if _HANDLER_2D is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLER_2D, 'WINDOW')
        except Exception:
            pass
        _HANDLER_2D = None
    _DIM_HIT_RECTS.clear()
    tag_redraw_all()


def shutdown():
    """Clean up runtime overlay state when the extension is disabled."""
    clear_modal()
    remove_handlers()
