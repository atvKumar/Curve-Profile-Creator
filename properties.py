import json
import math
import bpy
from mathutils import Matrix
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .architectural_recipes import ARCHITECTURAL_COMPONENT_ITEMS
from .constructed_shapes import CONSTRUCTED_SHAPE_ITEMS
from . import compound_geometry, primitive_geometry, user_profiles


def _profile_poll(_self, obj):
    return bool(obj and obj.type == 'CURVE' and obj.get("cpc_profile"))


PARAMETRIC_PART_ITEMS = (
    ('LINE', "Line / Fascia", "Straight architectural member"),
    ('OVOLO', "Ovolo / Convex Quarter Round", "Convex projecting circular or elliptical quarter-round"),
    ('CAVETTO', "Cavetto / Concave Cove", "Concave recessed circular or elliptical quarter-hollow"),
    ('TORUS', "Half Round / Torus", "Convex semicircular or semi-elliptical roll"),
    ('CYMA_RECTA', "Cyma Recta / Ogee", "Two-arc compass cyma, concave/convex S profile"),
    ('CYMA_REVERSA', "Cyma Reversa", "Opposite two-arc compass cyma / reverse ogee"),
)

PARAMETRIC_SHAPE_ITEMS = (
    ('CIRCLE', "Circular", "Use circular quarter/half-round proportions"),
    ('ELLIPSE', "Elliptical", "Use independent X/Y radii"),
)

PARAMETRIC_ARC_CONSTRUCTION_ITEMS = (
    ('ARC_DEPTH', "Circular / Arc Depth", "True circular construction; most members use Arc Depth, Cyma uses a coupled G1 biarc, and Classical Scotia derives its two radii from Height + Projection"),
    ('FULLNESS', "Fullness", "Alternate CPC conic Fullness construction for optical shaping"),
)

VIEWPORT_UNIT_ITEMS = (
    ('SCENE', "Scene", "Use Blender scene units for viewport dimensions and typed values"),
    ('METRIC', "Metric", "Display profile dimensions in architecture-oriented metric units; unitless HUD input is millimetres"),
    ('ARCH', "Architectural", "Display and enter feet, inches and reduced fractions"),
)

IMPERIAL_FRACTION_ITEMS = (
    ('2', '1/2"', "Round Architectural display to the nearest half inch"),
    ('4', '1/4"', "Round Architectural display to the nearest quarter inch"),
    ('8', '1/8"', "Round Architectural display to the nearest eighth inch"),
    ('16', '1/16"', "Round Architectural display to the nearest sixteenth inch"),
    ('32', '1/32"', "Round Architectural display to the nearest thirty-second inch"),
)


def _arc_radius(chord, depth):
    try:
        return primitive_geometry.arc_radius_from_chord_depth(chord, depth)
    except Exception:
        return 0.0


def _get_parametric_arc_radius(self):
    return _arc_radius(getattr(self, "parametric_width", 0.05), getattr(self, "parametric_arc_depth", 0.01))


def _get_arch_arc_radius(self):
    return _arc_radius(getattr(self, "arch_width", 0.03), getattr(self, "arch_arc_depth", 0.006))


def _get_arch_secondary_arc_radius(self):
    return _arc_radius(
        getattr(self, "arch_secondary_width", 0.02),
        getattr(self, "arch_secondary_arc_depth", 0.0041421356),
    )


def _get_object_parametric_arc_radius(self):
    return _arc_radius(getattr(self, "cpc_param_width", 0.05), getattr(self, "cpc_param_arc_depth", 0.01))


def _get_object_arch_arc_radius(self):
    return _arc_radius(getattr(self, "cpc_arch_width", 0.03), getattr(self, "cpc_arch_arc_depth", 0.006))


def _get_object_arch_secondary_arc_radius(self):
    return _arc_radius(
        getattr(self, "cpc_arch_secondary_width", 0.02),
        getattr(self, "cpc_arch_secondary_arc_depth", 0.0041421356),
    )


# Session-local baseline cache for committed-profile live adjustment.  The
# visible curve data is always regenerated from this baseline, so dragging
# scale/rotation controls is absolute and does not accumulate numerical drift.
_PROFILE_ADJUST_BASELINES = {}


def _profile_key(profile):
    try:
        return int(profile.as_pointer())
    except Exception:
        return id(profile)


def _snapshot_curve_geometry(curve):
    snapshot = []
    for spline in curve.splines:
        item = {
            "type": spline.type,
            "cyclic": bool(spline.use_cyclic_u),
        }
        if spline.type == 'BEZIER':
            item["points"] = [
                (
                    tuple(bp.co),
                    tuple(bp.handle_left),
                    tuple(bp.handle_right),
                )
                for bp in spline.bezier_points
            ]
        else:
            item["points"] = [tuple(p.co) for p in spline.points]
        snapshot.append(item)
    return snapshot


def _snapshot_matches_curve(snapshot, curve):
    if snapshot is None or len(snapshot) != len(curve.splines):
        return False
    for item, spline in zip(snapshot, curve.splines):
        if item.get("type") != spline.type:
            return False
        count = len(spline.bezier_points) if spline.type == 'BEZIER' else len(spline.points)
        if len(item.get("points", ())) != count:
            return False
    return True


def _restore_curve_geometry(curve, snapshot):
    if not _snapshot_matches_curve(snapshot, curve):
        return False
    for item, spline in zip(snapshot, curve.splines):
        if spline.type == 'BEZIER':
            for bp, values in zip(spline.bezier_points, item["points"]):
                co, left, right = values
                bp.co = co
                bp.handle_left = left
                bp.handle_right = right
        else:
            for point, co in zip(spline.points, item["points"]):
                point.co = co
    return True


def capture_profile_adjust_baseline(profile):
    if not profile or profile.type != 'CURVE':
        return
    _PROFILE_ADJUST_BASELINES[_profile_key(profile)] = _snapshot_curve_geometry(profile.data)


def _refresh_profile_dependents(context, profile):
    if not profile or profile.type != 'CURVE':
        return
    profile.data.update_tag()
    profile.update_tag()
    for obj in bpy.data.objects:
        if obj.type == 'CURVE' and obj != profile and getattr(obj.data, "bevel_object", None) == profile:
            obj.data.update_tag()
            obj.update_tag()
    try:
        context.view_layer.update()
    except Exception:
        pass
    wm = getattr(context, "window_manager", None)
    if wm:
        for window in wm.windows:
            screen = window.screen
            if not screen:
                continue
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()


def _set_adjust_guard(settings, value):
    scene = getattr(settings, "id_data", None)
    if scene is not None:
        scene["_cpc_profile_adjust_guard"] = bool(value)


def _adjust_guarded(settings):
    scene = getattr(settings, "id_data", None)
    return bool(scene and scene.get("_cpc_profile_adjust_guard", False))


def _reset_adjustment_controls(settings):
    _set_adjust_guard(settings, True)
    try:
        settings.profile_adjust_scale_x = 1.0
        settings.profile_adjust_scale_y = 1.0
        settings.profile_adjust_rotation = 0.0
    finally:
        _set_adjust_guard(settings, False)


def _apply_live_profile_adjustment(settings, context, source=None):
    if _adjust_guarded(settings):
        return
    profile = settings.active_profile
    if not profile or profile.type != 'CURVE':
        return

    # Uniform scale follows whichever scale field the user is actively editing.
    if settings.profile_adjust_uniform_scale and source in {'X', 'Y'}:
        _set_adjust_guard(settings, True)
        try:
            if source == 'X':
                settings.profile_adjust_scale_y = settings.profile_adjust_scale_x
            else:
                settings.profile_adjust_scale_x = settings.profile_adjust_scale_y
        finally:
            _set_adjust_guard(settings, False)

    key = _profile_key(profile)
    baseline = _PROFILE_ADJUST_BASELINES.get(key)
    if not _snapshot_matches_curve(baseline, profile.data):
        capture_profile_adjust_baseline(profile)
        baseline = _PROFILE_ADJUST_BASELINES.get(key)
    if not _restore_curve_geometry(profile.data, baseline):
        return

    sx = max(0.001, float(settings.profile_adjust_scale_x))
    sy = max(0.001, float(settings.profile_adjust_scale_y))
    angle = float(settings.profile_adjust_rotation)
    matrix = Matrix.Rotation(angle, 4, 'Z') @ Matrix.Diagonal((sx, sy, 1.0, 1.0))
    profile.data.transform(matrix)
    _refresh_profile_dependents(context, profile)


def _update_profile_scale_x(self, context):
    _apply_live_profile_adjustment(self, context, source='X')


def _update_profile_scale_y(self, context):
    _apply_live_profile_adjustment(self, context, source='Y')


def _update_profile_rotation(self, context):
    _apply_live_profile_adjustment(self, context, source='ROT')


def _update_uniform_scale(self, context):
    if _adjust_guarded(self) or not self.profile_adjust_uniform_scale:
        return
    _set_adjust_guard(self, True)
    try:
        self.profile_adjust_scale_y = self.profile_adjust_scale_x
    finally:
        _set_adjust_guard(self, False)
    _apply_live_profile_adjustment(self, context, source='X')


def _update_smooth_angle(self, context):
    obj = getattr(context, "object", None)
    if not obj:
        return
    try:
        from . import geometry
        geometry.update_cpc_smooth_angle(obj, self.smooth_angle)
    except Exception as exc:
        print(f"[Curve Profile Creator] Smooth by Angle update warning: {exc}")


def _update_smooth_enabled(self, context):
    obj = getattr(context, "object", None)
    if not obj:
        return
    # Disabling only removes CPC-owned copies; never touch a user's manually
    # added Smooth by Angle modifier. Enabling on an existing active sweep uses
    # Blender's bundled asset in the same way as new sweeps.
    try:
        from . import geometry
        if self.smooth_by_angle:
            if obj.type == 'CURVE' and (obj.get("cpc_sweep") or getattr(obj.data, "bevel_object", None)):
                geometry.ensure_smooth_by_angle(context, obj, self.smooth_angle, enabled=True)
        else:
            geometry.remove_cpc_smooth_by_angle(obj)
    except Exception as exc:
        print(f"[Curve Profile Creator] Smooth by Angle toggle warning: {exc}")


def _active_profile_changed(self, context):
    if _adjust_guarded(self):
        return
    _reset_adjustment_controls(self)
    capture_profile_adjust_baseline(self.active_profile)


def bake_live_profile_adjustment(settings, profile=None):
    """Make the currently visible profile the new neutral live-adjust baseline."""
    profile = profile or settings.active_profile
    if not profile or profile.type != 'CURVE':
        return
    capture_profile_adjust_baseline(profile)
    _reset_adjustment_controls(settings)


def _cyma_orientation(primitive_id):
    return "RECTA" if str(primitive_id).upper() == "CYMA_RECTA" else "REVERSA"


def _cyma_primary_depth(width, height, bias, primitive_id):
    return compound_geometry.cyma_primary_depth(
        float(width), float(height), float(bias),
        orientation=_cyma_orientation(primitive_id),
    )


def _arch_cyma_primitive(component_id):
    component_id = str(component_id or "").upper()
    if component_id == "CYMA_RECTA_FILLETS":
        return "CYMA_RECTA"
    if component_id == "CYMA_REVERSA_FILLETS":
        return "CYMA_REVERSA"
    return ""


def _update_component_geometry(obj, _context):
    if not obj or obj.type != 'CURVE' or not obj.get("cpc_parametric"):
        return
    if obj.get("_cpc_param_initializing") or obj.get("_cpc_param_updating"):
        return

    obj["_cpc_param_updating"] = True
    try:
        from . import primitives
        settings = None
        if _context is not None and getattr(_context, "scene", None) is not None:
            settings = getattr(_context.scene, "cpc_settings", None)
        maintain_connected = bool(getattr(settings, "maintain_connected_parts", True))
        merge_tolerance = float(getattr(settings, "merge_tolerance", 0.0005))

        primitive_id = str(obj.get("cpc_primitive_id", "LINE"))
        if (
            primitive_id in {"CYMA_RECTA", "CYMA_REVERSA"}
            and obj.cpc_param_arc_construction_mode == 'ARC_DEPTH'
            and str(obj.get("cpc_construction", "")) != "CIRCULAR_BIARC_G1"
        ):
            # Switching Fullness -> Circular should preserve the current shape
            # degree of freedom by converting the current Bias into primary D.
            obj.cpc_param_arc_depth = _cyma_primary_depth(
                obj.cpc_param_width, obj.cpc_param_height, obj.cpc_param_bias, primitive_id
            )

        geometry = primitives.update_object_geometry(
            obj,
            width=obj.cpc_param_width,
            height=obj.cpc_param_height,
            shape_mode=obj.cpc_param_shape_mode,
            bias=obj.cpc_param_bias,
            fullness=obj.cpc_param_fullness,
            concave_fullness=obj.cpc_param_concave_fullness,
            convex_fullness=obj.cpc_param_convex_fullness,
            arc_construction_mode=obj.cpc_param_arc_construction_mode,
            arc_depth=obj.cpc_param_arc_depth,
            preserve_anchor=True,
            propagate_connected=maintain_connected,
            connection_tolerance=merge_tolerance,
        )
        if (
            geometry
            and primitive_id in {"CYMA_RECTA", "CYMA_REVERSA"}
            and geometry.parameters.get("arc_construction_mode") == "ARC_DEPTH"
        ):
            obj.cpc_param_arc_depth = float(geometry.parameters["arc_depth"])
            obj.cpc_param_bias = float(geometry.parameters["bias"])

        # Keep the hidden height value synchronized with circular geometry so
        # switching a placed circle to Elliptical begins from the same shape.
        if (geometry and "height" in geometry.parameters and obj.cpc_param_shape_mode == 'CIRCLE' and obj.cpc_param_arc_construction_mode == 'FULLNESS'):
            obj.cpc_param_height = float(geometry.parameters["height"])
    except Exception as exc:
        print(f"[Curve Profile Creator] live component update failed: {exc}")
    finally:
        obj["_cpc_param_updating"] = False


def _update_arch_component(obj, context):
    if not obj or not obj.get("cpc_arch_controller"):
        return
    if obj.get("_cpc_arch_initializing") or obj.get("_cpc_arch_updating"):
        return
    try:
        component_id = str(obj.get("cpc_arch_component_id", ""))
        cyma_primitive = _arch_cyma_primitive(component_id)
        if cyma_primitive and obj.cpc_arch_arc_construction_mode == 'ARC_DEPTH':
            try:
                previous = json.loads(str(obj.get("cpc_arch_parameters", "") or "{}"))
            except Exception:
                previous = {}
            if str(previous.get("arc_construction_mode", "FULLNESS")) != "ARC_DEPTH":
                obj["_cpc_arch_initializing"] = True
                try:
                    obj.cpc_arch_arc_depth = _cyma_primary_depth(
                        obj.cpc_arch_width, obj.cpc_arch_height, obj.cpc_arch_bias, cyma_primitive
                    )
                finally:
                    obj["_cpc_arch_initializing"] = False

        from . import architectural_components
        architectural_components.update_instance(obj, context)
    except Exception as exc:
        print(f"[Curve Profile Creator] architectural component update failed: {exc}")


def _update_part_rotation(obj, context):
    if not obj or not obj.get("cpc_part") or not obj.get("cpc_parametric") or obj.get("cpc_preview"):
        return
    if obj.get("_cpc_part_transform_initializing") or obj.get("_cpc_part_transform_updating"):
        return
    try:
        from . import primitives
        primitives.update_part_rotation(obj, context)
    except Exception as exc:
        print(f"[Curve Profile Creator] part rotation failed: {exc}")


@persistent
def _initialise_loaded_cpc_state(_dummy=None):
    """Restore runtime/UI state for files created with the 0.4.0+ baseline."""
    try:
        from . import architectural_components
        architectural_components.restore_loaded_instances(bpy.data.objects)
        for scene in bpy.data.scenes:
            if not hasattr(scene, "cpc_settings"):
                continue
            _reset_adjustment_controls(scene.cpc_settings)
            capture_profile_adjust_baseline(scene.cpc_settings.active_profile)
    except Exception as exc:
        print(f"[Curve Profile Creator] load-state warning: {exc}")



def _update_parametric_arc_mode(self, _context):
    primitive_id = str(getattr(self, "parametric_part", "LINE"))
    if primitive_id not in {"CYMA_RECTA", "CYMA_REVERSA"}:
        return
    if str(getattr(self, "parametric_arc_construction_mode", "FULLNESS")) != "ARC_DEPTH":
        return
    try:
        self.parametric_arc_depth = _cyma_primary_depth(
            self.parametric_width, self.parametric_height, self.cyma_bias, primitive_id
        )
    except Exception:
        pass


def _update_arch_arc_mode(self, _context):
    primitive_id = _arch_cyma_primitive(getattr(self, "arch_component", ""))
    if not primitive_id:
        return
    if str(getattr(self, "arch_arc_construction_mode", "FULLNESS")) != "ARC_DEPTH":
        return
    try:
        self.arch_arc_depth = _cyma_primary_depth(
            self.arch_width, self.arch_height, self.arch_bias, primitive_id
        )
    except Exception:
        pass


def _update_arch_component_defaults(self, _context):
    component_id = str(getattr(self, "arch_component", "") or "").upper()
    if component_id == 'CLASSICAL_SCOTIA':
        try:
            # Height/3 gives lower:upper radius = 2:1, a canonical compass
            # starting proportion while remaining directly editable through W/H.
            self.arch_arc_construction_mode = 'ARC_DEPTH'
            self.arch_width = max(float(self.arch_height) / 3.0, 0.0001)
            self.arch_fullness = 1.0
            self.arch_secondary_fullness = 1.0
        except Exception:
            pass
        return

    if component_id == 'NOSE_COVE':
        try:
            self.arch_arc_construction_mode = 'ARC_DEPTH'
            self.arch_arc_depth = primitive_geometry.default_torus_arc_depth(float(self.arch_width))
            self.arch_secondary_arc_depth = primitive_geometry.default_arc_depth(float(self.arch_secondary_width))
        except Exception:
            pass
        return

    primitive_id = _arch_cyma_primitive(component_id)
    if not primitive_id:
        return
    try:
        self.arch_arc_construction_mode = 'ARC_DEPTH'
        self.arch_arc_depth = _cyma_primary_depth(
            self.arch_width, self.arch_height, self.arch_bias, primitive_id
        )
    except Exception:
        pass


def _update_parametric_part_defaults(self, _context):
    """Apply only semantic starting values that differ by primitive.

    This is a pre-creation convenience, not a live constraint.  Once placed,
    Chord and Arc Depth remain independent so a Torus may intentionally become
    a shallower/deeper convex circular segment.
    """
    primitive_id = str(getattr(self, "parametric_part", "LINE"))
    try:
        width = float(getattr(self, "parametric_width", 0.05))
        if primitive_id in {'OVOLO', 'CAVETTO', 'TORUS'}:
            self.parametric_arc_construction_mode = 'ARC_DEPTH'
            self.parametric_arc_depth = primitive_geometry.default_arc_depth_for_primitive(
                primitive_id, width
            )
        elif primitive_id in {'CYMA_RECTA', 'CYMA_REVERSA'}:
            self.parametric_arc_construction_mode = 'ARC_DEPTH'
            self.parametric_arc_depth = _cyma_primary_depth(
                width,
                float(getattr(self, "parametric_height", 0.025)),
                float(getattr(self, "cyma_bias", 0.5)),
                primitive_id,
            )
    except Exception:
        pass


def _update_viewport_guides(self, context):
    try:
        from . import viewport_overlay
        if bool(getattr(self, "viewport_guides", True)):
            viewport_overlay.ensure_handlers()
        else:
            viewport_overlay.remove_handlers()
        viewport_overlay.tag_redraw_all(context)
    except Exception:
        pass


class CPC_PG_Settings(PropertyGroup):
    viewport_guides: BoolProperty(
        name="Viewport Guides",
        description="Show CPC transient anchor, HUD and snap-intent overlays in the 3D Viewport",
        default=True,
        update=_update_viewport_guides,
    )

    viewport_unit_mode: EnumProperty(
        name="Viewport Units",
        description="Display and typed-input unit system used by CPC viewport construction tools",
        items=VIEWPORT_UNIT_ITEMS,
        default='SCENE',
        update=_update_viewport_guides,
    )

    imperial_fraction_denominator: EnumProperty(
        name="Imperial Precision",
        description="Fraction precision used for Architectural Imperial viewport display; this does not quantize geometry",
        items=IMPERIAL_FRACTION_ITEMS,
        default='16',
        update=_update_viewport_guides,
    )

    show_precreation_parameters: BoolProperty(
        name="Pre-Creation Parameters",
        description="Show the initial mathematical dimensions used when placing a new component",
        default=False,
    )

    show_build_profile: BoolProperty(
        name="Build Profile",
        description="Expand the profile assembly and selected-component live-edit controls",
        default=True,
    )


    show_user_profiles: BoolProperty(
        name="User Profiles",
        description="Expand reusable user profile preset controls",
        default=True,
    )

    show_sweep: BoolProperty(
        name="Sweep",
        description="Expand committed-profile adjustment and sweep controls",
        default=False,
    )

    show_placement_advanced: BoolProperty(
        name="Placement Settings",
        description="Show less frequently changed placement and snapping settings",
        default=False,
    )

    show_commit_advanced: BoolProperty(
        name="Commit Advanced",
        description="Show Bézier preservation, sampling and merge controls",
        default=False,
    )

    show_sweep_advanced: BoolProperty(
        name="Sweep Advanced",
        description="Show path, smoothing and resolution controls",
        default=False,
    )

    show_user_profile_advanced: BoolProperty(
        name="User Profile Library Location",
        description="Show the User Profile library folder setting",
        default=False,
    )

    show_arch_component_parameters: BoolProperty(
        name="Packed Component Parameters",
        description="Show the packed parameter surface for the selected Constructed or Architectural component",
        default=False,
    )

    maintain_connected_parts: BoolProperty(
        name="Maintain Connected Parts",
        description=(
            "Keep endpoint-junction connections intact during semantic edits; the selected Edit Anchor stays fixed "
            "while the opposite junction side follows, and ordinary Blender G/Location moves the whole connected profile rigidly"
        ),
        default=True,
    )

    editing_profile_id: StringProperty(
        name="Editing Profile ID",
        description="Internal persistent ID of the committed profile currently reopened for component editing",
        default="",
        options={'HIDDEN'},
    )

    build_session_id: StringProperty(
        name="Build Session ID",
        description="Internal ID grouping uncommitted construction parts into the current profile build",
        default="",
        options={'HIDDEN'},
    )

    construction_kind: EnumProperty(
        name="Component Type",
        description="Choose a basic component, a constructed geometric shape, or an architectural composition",
        items=(
            ('BASIC', "Basic", "Place one mathematical CPC component"),
            ('CONSTRUCTED', "Constructed", "Place a packed shape assembled from canonical local line geometry"),
            ('ARCH', "Architectural", "Place a packed multi-part architectural component"),
        ),
        default='BASIC',
    )

    constructed_shape: EnumProperty(
        name="Constructed Shape",
        description="Geometric line assembly generated from canonical local points",
        items=CONSTRUCTED_SHAPE_ITEMS,
        default='CHAMFER',
    )

    arch_component: EnumProperty(
        name="Architectural Component",
        description="Common architectural composition built from ordinary CPC parts",
        items=ARCHITECTURAL_COMPONENT_ITEMS,
        default='OVOLO_FILLETS',
        update=_update_arch_component_defaults,
    )

    arch_width: FloatProperty(name="Width", default=0.030, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_height: FloatProperty(name="Height", default=0.030, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_fullness: FloatProperty(name="Fullness", default=1.0, min=0.2, max=1.8, precision=2)
    arch_arc_construction_mode: EnumProperty(
        name="Curve Construction",
        description="Use Fullness or true circular construction; Cyma uses a G1 biarc and Classical Scotia derives two tangent quarter-circle radii",
        items=PARAMETRIC_ARC_CONSTRUCTION_ITEMS,
        default='ARC_DEPTH',
        update=_update_arch_arc_mode,
    )
    arch_arc_depth: FloatProperty(
        name="Arc Depth",
        description="Arc Depth control; for Cyma Circular this is the primary lobe sagitta",
        default=0.0062132034,
        min=0.000001,
        soft_max=1.0,
        unit='LENGTH',
    )
    arch_arc_radius: FloatProperty(
        name="Radius",
        description="Derived circle radius from Chord and Arc Depth",
        unit='LENGTH',
        get=_get_arch_arc_radius,
    )
    arch_bias: FloatProperty(name="Cyma Bias", default=0.5, min=0.15, max=0.85, subtype='FACTOR')
    arch_concave_fullness: FloatProperty(name="Concave Fullness", default=1.0, min=0.2, max=1.8, precision=2)
    arch_convex_fullness: FloatProperty(name="Convex Fullness", default=1.0, min=0.2, max=1.8, precision=2)
    arch_fillet_a: FloatProperty(name="Fillet A", default=0.005, min=0.0001, soft_max=0.25, unit='LENGTH')
    arch_fillet_b: FloatProperty(name="Fillet B", default=0.005, min=0.0001, soft_max=0.25, unit='LENGTH')
    arch_equal_fillets: BoolProperty(name="Equal Fillets", default=True)
    arch_fascia: FloatProperty(name="Fascia", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_secondary_width: FloatProperty(name="Secondary Width", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_secondary_arc_depth: FloatProperty(
        name="Secondary Arc Depth",
        description="Independent Arc Depth of the secondary circular member; Nose + Cove uses this for the Cove",
        default=0.0041421356,
        min=0.000001,
        soft_max=1.0,
        unit='LENGTH',
    )
    arch_secondary_arc_radius: FloatProperty(
        name="Secondary Radius",
        description="Derived circle radius from the secondary Chord and Arc Depth",
        unit='LENGTH',
        get=_get_arch_secondary_arc_radius,
    )
    arch_secondary_height: FloatProperty(name="Secondary Height", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_secondary_fullness: FloatProperty(name="Secondary Fullness", default=1.0, min=0.2, max=1.8, precision=2)
    arch_tread1: FloatProperty(name="Tread 1", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_rise1: FloatProperty(name="Rise 1", default=0.015, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_tread2: FloatProperty(name="Tread 2", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_rise2: FloatProperty(name="Rise 2", default=0.015, min=0.0001, soft_max=1.0, unit='LENGTH')
    arch_equal_steps: BoolProperty(name="Equal Steps", default=True)

    parametric_part: EnumProperty(
        name="Component",
        description="Mathematically generated architectural component",
        items=PARAMETRIC_PART_ITEMS,
        default='LINE',
        update=_update_parametric_part_defaults,
    )

    parametric_shape_mode: EnumProperty(
        name="Arc Shape",
        description="Use true circular proportions or independent elliptical width/height",
        items=PARAMETRIC_SHAPE_ITEMS,
        default='CIRCLE',
    )

    parametric_arc_construction_mode: EnumProperty(
        name="Construction",
        description="Choose validated Fullness or true circular construction; Cyma uses a coupled G1 biarc",
        items=PARAMETRIC_ARC_CONSTRUCTION_ITEMS,
        default='ARC_DEPTH',
        update=_update_parametric_arc_mode,
    )

    parametric_arc_depth: FloatProperty(
        name="Arc Depth",
        description="Arc Depth control; for Cyma Circular this is the primary lobe sagitta",
        default=0.0103553391,
        min=0.000001,
        soft_max=1.0,
        unit='LENGTH',
    )

    parametric_arc_radius: FloatProperty(
        name="Radius",
        description="Derived circle radius from Chord and Arc Depth",
        unit='LENGTH',
        get=_get_parametric_arc_radius,
    )

    parametric_width: FloatProperty(
        name="Width",
        description="Local width/projection of the generated component",
        default=0.05,
        min=0.0001,
        soft_max=1.0,
        unit='LENGTH',
    )

    parametric_height: FloatProperty(
        name="Height",
        description="Local height of elliptical and compound components",
        default=0.025,
        min=0.0001,
        soft_max=1.0,
        unit='LENGTH',
    )

    cyma_bias: FloatProperty(
        name="Cyma Bias",
        description="Position of the G1 inflection join in the two-arc compass cyma",
        default=0.5,
        min=0.15,
        max=0.85,
        subtype='FACTOR',
    )

    parametric_fullness: FloatProperty(
        name="Fullness",
        description="Curve fullness inside the fixed endpoints; 1.00 is the canonical analytic arc, lower is flatter, higher is fuller",
        default=1.0,
        min=0.2,
        max=1.8,
        precision=2,
    )

    cyma_concave_fullness: FloatProperty(
        name="Concave Fullness",
        description="Fullness of the concave half; 1.00 preserves the canonical compass arc",
        default=1.0,
        min=0.2,
        max=1.8,
        precision=2,
    )

    cyma_convex_fullness: FloatProperty(
        name="Convex Fullness",
        description="Fullness of the convex half; 1.00 preserves the canonical compass arc",
        default=1.0,
        min=0.2,
        max=1.8,
        precision=2,
    )

    rotation_snap_degrees: FloatProperty(
        name="Rotation Snap",
        description="Angular increment used while holding Ctrl during free rotation",
        default=15.0,
        min=1.0,
        max=90.0,
    )

    snap_pixels: IntProperty(
        name="Snap Radius",
        description="Screen-space endpoint snap radius during modal placement",
        default=22,
        min=4,
        max=120,
    )

    preserve_bezier: BoolProperty(
        name="Preserve Bézier",
        description="Commit compatible CPC parts as clean Bézier splines with their meaningful handles; unsupported geometry falls back to sampled commit",
        default=True,
    )

    sample_resolution: IntProperty(
        name="Profile Resolution",
        description="Samples per Bézier span when sampled Commit is selected or Preserve Bézier must fall back for unsupported geometry",
        default=12,
        min=2,
        max=64,
    )

    merge_tolerance: FloatProperty(
        name="Merge Tolerance",
        description="Distance used to stitch touching part endpoints into continuous profile splines",
        default=0.0005,
        min=0.000001,
        soft_max=0.05,
        unit='LENGTH',
    )

    user_profile_library_path: StringProperty(
        name="User Profile Library",
        description="Optional folder for CPC .cpcprofile files and generated PNG thumbnails; blank uses Blender's extension user storage",
        subtype='DIR_PATH',
        default="",
        update=user_profiles.on_library_path_changed,
    )

    user_profile_category_filter: EnumProperty(
        name="Category",
        description="Filter the User Profile library by category; global Search temporarily ignores this filter",
        items=user_profiles.category_enum_items,
        update=user_profiles.on_category_filter_changed,
    )

    user_profile_search: StringProperty(
        name="Search",
        description="Search all User Profiles across categories by name, description, tags and source metadata",
        default="",
        update=user_profiles.on_search_changed,
    )

    user_profile_selected: EnumProperty(
        name="User Profile",
        description="Reusable CPC profile preset from the current category/global-search result set",
        items=user_profiles.enum_items,
    )

    active_profile: PointerProperty(
        name="Active Profile",
        description="Profile curve used for sweeps",
        type=bpy.types.Object,
        poll=_profile_poll,
        update=_active_profile_changed,
    )

    sweep_path_mode: EnumProperty(
        name="Path Mode",
        description="Auto creates horizontal coplanar selections as stable 2D paths; force 2D or 3D when required",
        items=(
            ('AUTO', "Auto Planar", "Use 2D for horizontal coplanar selected edges, otherwise 3D"),
            ('2D', "2D", "Force the generated path into its XY plane while preserving average Z elevation"),
            ('3D', "3D", "Always create a 3D path and use Blender twist calculation"),
        ),
        default='AUTO',
    )

    profile_adjust_uniform_scale: BoolProperty(
        name="Uniform Scale",
        description="Link X and Y while live-scaling the committed profile",
        default=True,
        update=_update_uniform_scale,
    )

    profile_adjust_scale_x: FloatProperty(
        name="Scale X",
        description="Live committed-profile X scale around its local anchor/origin",
        default=1.0,
        min=0.001,
        soft_max=10.0,
        precision=3,
        update=_update_profile_scale_x,
    )

    profile_adjust_scale_y: FloatProperty(
        name="Scale Y",
        description="Live committed-profile Y scale around its local anchor/origin",
        default=1.0,
        min=0.001,
        soft_max=10.0,
        precision=3,
        update=_update_profile_scale_y,
    )

    profile_adjust_rotation: FloatProperty(
        name="Rotation",
        description="Live committed-profile rotation around its local anchor/origin",
        default=0.0,
        unit='ROTATION',
        update=_update_profile_rotation,
    )

    path_resolution: IntProperty(
        name="Path Resolution",
        description="Curve interpolation resolution for generated sweep paths",
        default=4,
        min=1,
        max=64,
    )

    twist_mode: EnumProperty(
        name="Twist",
        description="How Blender calculates profile rotation along 3D paths",
        items=(
            ('MINIMUM', "Minimum", "Minimize twist along the path"),
            ('Z_UP', "Z Up", "Use the global Z direction as the up reference"),
            ('TANGENT', "Tangent", "Calculate twist from path tangents"),
        ),
        default='MINIMUM',
    )

    smooth_by_angle: BoolProperty(
        name="Smooth by Angle",
        description="Add Blender's bundled Smooth by Angle Geometry Nodes modifier to newly generated/applied sweeps",
        default=True,
        update=_update_smooth_enabled,
    )

    smooth_angle: FloatProperty(
        name="Smooth Angle",
        description="Maximum face angle treated as smooth by Blender's Smooth by Angle modifier",
        default=math.radians(30.0),
        min=0.0,
        max=math.pi,
        unit='ROTATION',
        update=_update_smooth_angle,
    )

    fill_caps: BoolProperty(
        name="Fill Caps",
        description="Cap open ends of the generated beveled curve when supported by the profile",
        default=False,
    )

    hide_builder_parts: BoolProperty(
        name="Hide Parts After Commit",
        description="Hide modular construction parts after creating the final profile",
        default=True,
    )


_CLASSES = (CPC_PG_Settings,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cpc_settings = PointerProperty(type=CPC_PG_Settings)

    bpy.types.Object.cpc_param_width = FloatProperty(
        name="Width",
        description="Live width/projection of this parametric component",
        default=0.05,
        min=0.0001,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_height = FloatProperty(
        name="Height",
        description="Live height of this parametric component",
        default=0.025,
        min=0.0001,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_shape_mode = EnumProperty(
        name="Arc Shape",
        description="Live circular or elliptical construction mode",
        items=PARAMETRIC_SHAPE_ITEMS,
        default='CIRCLE',
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_arc_construction_mode = EnumProperty(
        name="Construction",
        description="Live Fullness or true circular construction; Cyma uses a G1 biarc and Classical Scotia uses two derived quarter-circle radii",
        items=PARAMETRIC_ARC_CONSTRUCTION_ITEMS,
        default='ARC_DEPTH',
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_arc_depth = FloatProperty(
        name="Arc Depth",
        description="Live Arc Depth; for Cyma Circular this is the primary lobe sagitta",
        default=0.0103553391,
        min=0.000001,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_arc_radius = FloatProperty(
        name="Radius",
        description="Derived circle radius from Chord and Arc Depth",
        unit='LENGTH',
        get=_get_object_parametric_arc_radius,
    )
    bpy.types.Object.cpc_param_bias = FloatProperty(
        name="Cyma Bias",
        description="Live position of the G1 join in this compass cyma",
        default=0.5,
        min=0.15,
        max=0.85,
        subtype='FACTOR',
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_fullness = FloatProperty(
        name="Fullness",
        description="Live curve fullness; 1.00 is the canonical analytic arc",
        default=1.0,
        min=0.2,
        max=1.8,
        precision=2,
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_concave_fullness = FloatProperty(
        name="Concave Fullness",
        description="Live fullness of the concave half of a cyma",
        default=1.0,
        min=0.2,
        max=1.8,
        precision=2,
        update=_update_component_geometry,
    )
    bpy.types.Object.cpc_param_convex_fullness = FloatProperty(
        name="Convex Fullness",
        description="Live fullness of the convex half of a cyma",
        default=1.0,
        min=0.2,
        max=1.8,
        precision=2,
        update=_update_component_geometry,
    )

    # Packed public parameter surface for built-in Architectural Components.
    # Only the controller object in an instance owns meaningful values; selecting
    # any child resolves back to that controller in the UI.
    bpy.types.Object.cpc_arch_width = FloatProperty(name="Width", default=0.030, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_height = FloatProperty(name="Height", default=0.030, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_fullness = FloatProperty(name="Fullness", default=1.0, min=0.2, max=1.8, precision=2, update=_update_arch_component)
    bpy.types.Object.cpc_arch_arc_construction_mode = EnumProperty(
        name="Curve Construction",
        description="Packed Fullness or true circular construction; Cyma uses a G1 biarc and Classical Scotia uses two derived quarter-circle radii",
        items=PARAMETRIC_ARC_CONSTRUCTION_ITEMS,
        default='ARC_DEPTH',
        update=_update_arch_component,
    )
    bpy.types.Object.cpc_arch_arc_depth = FloatProperty(
        name="Arc Depth",
        description="Packed sagitta/depth of the primary circular segment",
        default=0.0062132034,
        min=0.000001,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_arch_component,
    )
    bpy.types.Object.cpc_arch_arc_radius = FloatProperty(
        name="Radius",
        description="Derived circle radius from packed Chord and Arc Depth",
        unit='LENGTH',
        get=_get_object_arch_arc_radius,
    )
    bpy.types.Object.cpc_arch_bias = FloatProperty(name="Cyma Bias", default=0.5, min=0.15, max=0.85, subtype='FACTOR', update=_update_arch_component)
    bpy.types.Object.cpc_arch_concave_fullness = FloatProperty(name="Concave Fullness", default=1.0, min=0.2, max=1.8, precision=2, update=_update_arch_component)
    bpy.types.Object.cpc_arch_convex_fullness = FloatProperty(name="Convex Fullness", default=1.0, min=0.2, max=1.8, precision=2, update=_update_arch_component)
    bpy.types.Object.cpc_arch_fillet_a = FloatProperty(name="Fillet A", default=0.005, min=0.0001, soft_max=0.25, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_fillet_b = FloatProperty(name="Fillet B", default=0.005, min=0.0001, soft_max=0.25, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_equal_fillets = BoolProperty(name="Equal Fillets", default=True, update=_update_arch_component)
    bpy.types.Object.cpc_arch_fascia = FloatProperty(name="Fascia", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_secondary_width = FloatProperty(name="Secondary Width", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_secondary_arc_depth = FloatProperty(
        name="Secondary Arc Depth",
        description="Independent packed Arc Depth of the secondary circular member",
        default=0.0041421356,
        min=0.000001,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_arch_component,
    )
    bpy.types.Object.cpc_arch_secondary_arc_radius = FloatProperty(
        name="Secondary Radius",
        description="Derived circle radius from the packed secondary Chord and Arc Depth",
        unit='LENGTH',
        get=_get_object_arch_secondary_arc_radius,
    )
    bpy.types.Object.cpc_arch_secondary_height = FloatProperty(name="Secondary Height", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_secondary_fullness = FloatProperty(name="Secondary Fullness", default=1.0, min=0.2, max=1.8, precision=2, update=_update_arch_component)
    bpy.types.Object.cpc_arch_tread1 = FloatProperty(name="Tread 1", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_rise1 = FloatProperty(name="Rise 1", default=0.015, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_tread2 = FloatProperty(name="Tread 2", default=0.020, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_rise2 = FloatProperty(name="Rise 2", default=0.015, min=0.0001, soft_max=1.0, unit='LENGTH', update=_update_arch_component)
    bpy.types.Object.cpc_arch_equal_steps = BoolProperty(name="Equal Steps", default=True, update=_update_arch_component)
    bpy.types.Object.cpc_part_rotation = FloatProperty(
        name="Part Rotation",
        description="Rotate this CPC construction part around its chosen Edit Anchor; the opposite endpoint-junction side follows according to Maintain Connected Parts",
        default=0.0,
        unit='ROTATION',
        update=_update_part_rotation,
    )

    if _initialise_loaded_cpc_state not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_initialise_loaded_cpc_state)
    _initialise_loaded_cpc_state()


def unregister():
    if _initialise_loaded_cpc_state in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_initialise_loaded_cpc_state)

    for attr in (
        "cpc_part_rotation",
        "cpc_arch_equal_steps",
        "cpc_arch_rise2",
        "cpc_arch_tread2",
        "cpc_arch_rise1",
        "cpc_arch_tread1",
        "cpc_arch_secondary_fullness",
        "cpc_arch_secondary_height",
        "cpc_arch_secondary_arc_radius",
        "cpc_arch_secondary_arc_depth",
        "cpc_arch_secondary_width",
        "cpc_arch_fascia",
        "cpc_arch_equal_fillets",
        "cpc_arch_fillet_b",
        "cpc_arch_fillet_a",
        "cpc_arch_convex_fullness",
        "cpc_arch_concave_fullness",
        "cpc_arch_bias",
        "cpc_arch_arc_radius",
        "cpc_arch_arc_depth",
        "cpc_arch_arc_construction_mode",
        "cpc_arch_fullness",
        "cpc_arch_height",
        "cpc_arch_width",
        "cpc_param_convex_fullness",
        "cpc_param_concave_fullness",
        "cpc_param_fullness",
        "cpc_param_bias",
        "cpc_param_arc_radius",
        "cpc_param_arc_depth",
        "cpc_param_arc_construction_mode",
        "cpc_param_shape_mode",
        "cpc_param_height",
        "cpc_param_width",
    ):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)

    if hasattr(bpy.types.Scene, "cpc_settings"):
        del bpy.types.Scene.cpc_settings
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
