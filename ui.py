import bpy
from bpy.types import Panel

from . import architectural_components, architectural_recipes, compound_geometry, placement_parameters, primitives, user_profiles, viewport_overlay
from . import EXTENSION_VERSION


def _section_header(box, settings, prop_name, label, icon):
    expanded = bool(getattr(settings, prop_name))
    row = box.row(align=True)
    row.prop(
        settings,
        prop_name,
        text=label,
        icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
        emboss=False,
    )
    row.label(text="", icon=icon)
    return expanded


def _disclosure(layout, owner, prop_name, label):
    expanded = bool(getattr(owner, prop_name))
    row = layout.row(align=True)
    row.prop(
        owner,
        prop_name,
        text=label,
        icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
        emboss=False,
    )
    return expanded


def _draw_arc_intent(layout, primitive_id):
    if primitive_id == 'OVOLO':
        info = layout.row()
        info.enabled = False
        info.label(text="Convex • projecting arc")
    elif primitive_id == 'CAVETTO':
        info = layout.row()
        info.enabled = False
        info.label(text="Concave • recessed / hollow arc")


def _draw_primitive_params(layout, owner, primitive_id, prefix="parametric_"):
    """Draw one CPC primitive parameter surface for settings or an Object."""
    def prop(name, text=None, **kwargs):
        layout.prop(owner, prefix + name, text=text or "", **kwargs)

    if primitive_id == 'LINE':
        prop("width", "Length")
        return

    if primitive_id in {'OVOLO', 'CAVETTO', 'TORUS'}:
        prop("arc_construction_mode", "Construction")
        mode = getattr(owner, prefix + "arc_construction_mode")
        if mode == 'ARC_DEPTH':
            row = layout.row(align=True)
            row.prop(owner, prefix + "width", text="Chord")
            row.prop(owner, prefix + "arc_depth", text="Depth")
            radius = layout.row()
            radius.enabled = False
            radius.prop(owner, prefix + "arc_radius", text="Radius")
            if primitive_id == 'TORUS':
                hint = layout.row()
                hint.enabled = False
                hint.label(text="Depth = Chord / 2 gives a true semicircle")
        else:
            prop("shape_mode", "Arc Shape")
            row = layout.row(align=True)
            row.prop(owner, prefix + "width", text="Width")
            if getattr(owner, prefix + "shape_mode") == 'ELLIPSE':
                row.prop(owner, prefix + "height", text="Height")
            prop("fullness", "Fullness")
        return

    if primitive_id in {'CYMA_RECTA', 'CYMA_REVERSA'}:
        prop("arc_construction_mode", "Construction")
        row = layout.row(align=True)
        row.prop(owner, prefix + "width", text="Width")
        row.prop(owner, prefix + "height", text="Height")
        if getattr(owner, prefix + "arc_construction_mode") == 'ARC_DEPTH':
            prop("arc_depth", "Primary Arc Depth")
            info = layout.row()
            info.enabled = False
            info.label(text="Circular biarc • G1 join • companion lobe is derived")
        else:
            prop("bias", "Bias")
            row = layout.row(align=True)
            row.prop(owner, prefix + "concave_fullness", text="Concave")
            row.prop(owner, prefix + "convex_fullness", text="Convex")


def _draw_arch_params(layout, owner, component_id, prefix="arch_"):
    """Draw the curated packed public parameters for one Architectural Component."""
    def prop(name, text=None, **kwargs):
        layout.prop(owner, prefix + name, text=text or "", **kwargs)

    fillet_components = {
        'OVOLO_FILLETS', 'CAVETTO_FILLETS',
        'CYMA_RECTA_FILLETS', 'CYMA_REVERSA_FILLETS',
    }
    quarter_components = {'OVOLO_FILLETS', 'CAVETTO_FILLETS'}
    cyma_components = {'CYMA_RECTA_FILLETS', 'CYMA_REVERSA_FILLETS'}
    fascia_components = {'FASCIA_OVOLO_FILLET', 'FASCIA_CAVETTO_FILLET'}
    arc_depth_components = quarter_components | fascia_components | {'SIMPLE_SCOTIA'}

    if component_id == 'CHAMFER':
        row = layout.row(align=True)
        row.prop(owner, prefix + "width", text="Run")
        row.prop(owner, prefix + "height", text="Rise")
        prop("fillet_a", "Fillet")
        hint = layout.row()
        hint.enabled = False
        hint.label(text="Equal horizontal fillets • diagonal angle derived from Run/Rise")

    if component_id == 'V_GROOVE':
        row = layout.row(align=True)
        row.prop(owner, prefix + "width", text="Width")
        row.prop(owner, prefix + "height", text="Depth")
        hint = layout.row()
        hint.enabled = False
        hint.label(text="Centered V • both flank angles derived from local points")

    if component_id == 'REBATE':
        row = layout.row(align=True)
        row.prop(owner, prefix + "width", text="Width")
        row.prop(owner, prefix + "height", text="Depth")
        hint = layout.row()
        hint.enabled = False
        hint.label(text="Three-line rectangular recess • no stored child angles")

    if component_id in arc_depth_components:
        prop("arc_construction_mode", "Construction")
        if getattr(owner, prefix + "arc_construction_mode") == 'ARC_DEPTH':
            row = layout.row(align=True)
            row.prop(owner, prefix + "width", text="Chord")
            row.prop(owner, prefix + "arc_depth", text="Depth")
            radius = layout.row()
            radius.enabled = False
            radius.prop(owner, prefix + "arc_radius", text="Radius")
        else:
            row = layout.row(align=True)
            row.prop(owner, prefix + "width", text="Width")
            row.prop(owner, prefix + "height", text="Height")
            prop("fullness", "Fullness")

    if component_id in cyma_components:
        prop("arc_construction_mode", "Construction")
        row = layout.row(align=True)
        row.prop(owner, prefix + "width", text="Width")
        row.prop(owner, prefix + "height", text="Height")
        if getattr(owner, prefix + "arc_construction_mode") == 'ARC_DEPTH':
            prop("arc_depth", "Primary Arc Depth")
            info = layout.row()
            info.enabled = False
            info.label(text="Circular biarc • G1 join • companion lobe is derived")
        else:
            prop("bias", "Cyma Bias")
            row = layout.row(align=True)
            row.prop(owner, prefix + "concave_fullness", text="Concave")
            row.prop(owner, prefix + "convex_fullness", text="Convex")

    if component_id in fillet_components:
        prop("equal_fillets", "Equal Fillets")
        if getattr(owner, prefix + "equal_fillets"):
            prop("fillet_a", "Fillet")
        else:
            row = layout.row(align=True)
            row.prop(owner, prefix + "fillet_a", text="Start Fillet")
            row.prop(owner, prefix + "fillet_b", text="End Fillet")

    if component_id in fascia_components:
        prop("fascia", "Fascia")
        prop("fillet_a", "End Fillet")

    if component_id == 'NOSE_COVE':
        prop("arc_construction_mode", "Construction")
        if getattr(owner, prefix + "arc_construction_mode") == 'ARC_DEPTH':
            row = layout.row(align=True)
            row.prop(owner, prefix + "width", text="Nose Chord")
            row.prop(owner, prefix + "arc_depth", text="Nose Depth")
            radius = layout.row()
            radius.enabled = False
            radius.prop(owner, prefix + "arc_radius", text="Nose Radius")

            row = layout.row(align=True)
            row.prop(owner, prefix + "secondary_width", text="Cove Chord")
            row.prop(owner, prefix + "secondary_arc_depth", text="Cove Depth")
            radius = layout.row()
            radius.enabled = False
            radius.prop(owner, prefix + "secondary_arc_radius", text="Cove Radius")

            hint = layout.row()
            hint.enabled = False
            hint.label(text="New Nose default: Depth = Chord / 2 (true half-round)")
        else:
            # Fullness remains the alternate construction mode.
            row = layout.row(align=True)
            row.prop(owner, prefix + "width", text="Nose Width")
            row.prop(owner, prefix + "fullness", text="Nose Fullness")
            row = layout.row(align=True)
            row.prop(owner, prefix + "secondary_width", text="Cove Width")
            row.prop(owner, prefix + "secondary_height", text="Cove Height")
            prop("secondary_fullness", "Cove Fullness")

    if component_id == 'CLASSICAL_SCOTIA':
        prop("arc_construction_mode", "Construction")
        row = layout.row(align=True)
        row.prop(owner, prefix + "width", text="Projection")
        row.prop(owner, prefix + "height", text="Height")
        try:
            solution = compound_geometry.solve_classical_scotia(
                float(getattr(owner, prefix + "height")),
                float(getattr(owner, prefix + "width")),
            )
            info = layout.row()
            info.enabled = False
            info.label(text=f"Lower : Upper radius = {solution.radius_ratio:.2f} : 1")
        except Exception:
            pass
        if getattr(owner, prefix + "arc_construction_mode") == 'FULLNESS':
            row = layout.row(align=True)
            row.prop(owner, prefix + "fullness", text="Upper Fullness")
            row.prop(owner, prefix + "secondary_fullness", text="Lower Fullness")
            info = layout.row()
            info.enabled = False
            info.label(text="Optical shaping • endpoints and G1 tangent preserved")
        else:
            info = layout.row()
            info.enabled = False
            info.label(text="Two exact quarter circles • centres aligned • G1 join")

    if component_id == 'SINGLE_STEP':
        row = layout.row(align=True)
        row.prop(owner, prefix + "tread1", text="Tread")
        row.prop(owner, prefix + "rise1", text="Rise")

    if component_id == 'DOUBLE_STEP':
        prop("equal_steps", "Equal Steps")
        row = layout.row(align=True)
        row.prop(owner, prefix + "tread1", text="Tread 1")
        row.prop(owner, prefix + "rise1", text="Rise 1")
        if not getattr(owner, prefix + "equal_steps"):
            row = layout.row(align=True)
            row.prop(owner, prefix + "tread2", text="Tread 2")
            row.prop(owner, prefix + "rise2", text="Rise 2")


def _selected_cpc_part(context):
    obj = context.object
    if not obj or obj.type != 'CURVE':
        return None
    if not obj.get("cpc_part") or not obj.get("cpc_parametric") or obj.get("cpc_preview"):
        return None
    return obj


class CPC_PT_Main(Panel):
    bl_label = "Curve Profile Creator"
    bl_idname = "CPC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Profile"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.cpc_settings
        row = layout.row(align=True)
        row.label(text=f"Version {EXTENSION_VERSION} • Interactive Viewport", icon='INFO')
        row.prop(settings, "viewport_guides", text="", icon='OVERLAY', toggle=True)

        self._draw_construction(layout, context, settings)
        self._draw_build(layout, context, settings)
        self._draw_user_profiles(layout, context, settings)
        self._draw_sweep(layout, context, settings)

    def _draw_construction(self, layout, context, settings):
        box = layout.box()
        box.label(text="1. Add Component", icon='CURVE_BEZCURVE')
        box.prop(settings, "construction_kind", expand=True)

        if settings.construction_kind == 'BASIC':
            box.prop(settings, "parametric_part", text="Component")
            part = settings.parametric_part
            _draw_arc_intent(box, part)
        elif settings.construction_kind == 'CONSTRUCTED':
            box.prop(settings, "constructed_shape", text="Shape")
            part = settings.constructed_shape
        else:
            box.prop(settings, "arch_component", text="Component")
            part = settings.arch_component

        if _disclosure(box, settings, "show_precreation_parameters", "Initial Parameters"):
            params = box.box()
            if settings.construction_kind in {'ARCH', 'CONSTRUCTED'}:
                _draw_arch_params(params, settings, part, prefix="arch_")
            else:
                _draw_primitive_params(params, settings, part, prefix="parametric_")

        if settings.construction_kind in {'ARCH', 'CONSTRUCTED'}:
            label = "Place Constructed Shape" if settings.construction_kind == 'CONSTRUCTED' else "Place Architectural Component"
            box.operator("cpc.place_architectural_component", text=label, icon='ADD')
        else:
            box.operator("cpc.place_part", text="Place Component", icon='ADD')

        if _disclosure(box, settings, "show_placement_advanced", "Placement Settings"):
            advanced = box.box()
            row = advanced.row(align=True)
            row.prop(settings, "snap_pixels", text="Snap Radius")
            row.prop(settings, "rotation_snap_degrees", text="Rotation Snap°")
            advanced.label(text="Semantic snaps: endpoint/origin → tangent → midpoint")
            advanced.label(text="Tab endpoint • X/Y flip • Wheel scale • A auto-align • R rotate")
            if settings.construction_kind in {'ARCH', 'CONSTRUCTED'}:
                component_id = settings.constructed_shape if settings.construction_kind == 'CONSTRUCTED' else settings.arch_component
                param_map = placement_parameters.architectural_parameters(
                    component_id,
                    architectural_components.scene_parameters(settings, component_id),
                )
            else:
                param_map = placement_parameters.basic_parameters(
                    settings.parametric_part,
                    arc_mode=settings.parametric_arc_construction_mode,
                    shape_mode=settings.parametric_shape_mode,
                )
            shortcut_text = placement_parameters.shortcut_text(param_map)
            if shortcut_text:
                advanced.label(text=shortcut_text + " • LMB commit • Esc cancel")
            note = advanced.row()
            note.enabled = False
            note.label(text="Only semantic parameters valid for the selected component are shown")

    def _draw_selected_part(self, box, context, settings, selected):
        primitive_id = str(selected.get("cpc_primitive_id", "LINE"))
        primitive_name = str(selected.get("cpc_primitive_name", primitive_id))
        role = str(selected.get("cpc_role", "") or "").replace('_', ' ').title()
        arch_controller = architectural_components.controller_for(selected) if selected.get("cpc_arch_instance_id") else None

        selected_box = box.box()
        title = role or primitive_name
        if arch_controller:
            group_parts = architectural_components.instance_parts(arch_controller)
            index = int(selected.get("cpc_arch_part_index", 0)) + 1
            selected_box.label(text=f"Selected Part • {title} • {index}/{len(group_parts)}", icon='ORIENTATION_LOCAL')
        else:
            selected_box.label(text=f"Selected Part • {primitive_name}", icon='ORIENTATION_LOCAL')
            _draw_arc_intent(selected_box, primitive_id)
            _draw_primitive_params(selected_box, selected, primitive_id, prefix="cpc_param_")

        # One interaction surface for semantic viewport dimensions + units.
        row = selected_box.row(align=True)
        if viewport_overlay.dimension_edit_active():
            row.operator("cpc.viewport_dimension_edit", text="Viewport Edit Active (E)", icon='CHECKMARK')
        else:
            row.operator("cpc.viewport_dimension_edit", text="Edit Dimensions in Viewport (E)", icon='EDITMODE_HLT')
        row.prop(settings, "viewport_unit_mode", text="")
        if settings.viewport_unit_mode == 'ARCH':
            row.prop(settings, "imperial_fraction_denominator", text="")

        # Universal CPC edit-anchor + rotation surface. The chosen endpoint stays
        # fixed for semantic dimensions and CPC Part Rotation; the opposite
        # endpoint-junction side follows.
        row = selected_box.row(align=True)
        row.label(text="Edit Anchor")
        op = row.operator(
            "cpc.set_edit_anchor",
            text="Start ✓" if int(selected.get("cpc_anchor_index", 0)) == 0 else "Start",
        )
        op.anchor = 0
        op = row.operator(
            "cpc.set_edit_anchor",
            text="End ✓" if int(selected.get("cpc_anchor_index", 0)) == 1 else "End",
        )
        op.anchor = 1

        selected_box.prop(selected, "cpc_part_rotation", text="Rotation")
        snap = float(settings.rotation_snap_degrees)
        row = selected_box.row(align=True)
        op = row.operator("cpc.adjust_part_rotation", text=f"−{snap:g}°")
        op.action = 'NEGATIVE'
        op = row.operator("cpc.adjust_part_rotation", text="Reset")
        op.action = 'RESET'
        op = row.operator("cpc.adjust_part_rotation", text=f"+{snap:g}°")
        op.action = 'POSITIVE'

        anchor_name = "End" if int(selected.get("cpc_anchor_index", 0)) else "Start"
        connected_count = primitives.connected_moving_side_count(selected)
        info = selected_box.row()
        info.enabled = False
        suffix = f" • {connected_count} on moving side" if connected_count else ""
        info.label(text=f"{anchor_name} Edit Anchor fixed{suffix}")

        # Packed geometry remains contextual; child geometry itself is not exposed
        # as a second competing edit surface.
        if arch_controller:
            component_id = str(arch_controller.get("cpc_arch_component_id", ""))
            component_name = str(arch_controller.get("cpc_arch_component_name", component_id))
            group = str(arch_controller.get("cpc_component_group", "") or "")
            if not group:
                group = architectural_recipes.component_group(component_id)
            group_label = "Constructed Shape" if group == "CONSTRUCTED" else "Architectural Component"
            if _disclosure(selected_box, settings, "show_arch_component_parameters", f"{group_label} • {component_name}"):
                packed = selected_box.box()
                _draw_arch_params(packed, arch_controller, component_id, prefix="cpc_arch_")
                note = packed.row()
                note.enabled = False
                note.label(text="Packed regeneration • selected Edit Anchor respected")

        selected_box.prop(settings, "maintain_connected_parts", text="Maintain Connected Parts")

    def _draw_build(self, layout, context, settings):
        box = layout.box()
        if not _section_header(box, settings, "show_build_profile", "2. Build Profile", 'MOD_CURVE'):
            return

        selected = _selected_cpc_part(context)
        if selected:
            self._draw_selected_part(box, context, settings, selected)
        else:
            info = box.row()
            info.enabled = False
            info.label(text="Select a CPC construction part to edit it")

        editing_profile_id = str(getattr(settings, "editing_profile_id", "") or "").strip()
        if editing_profile_id:
            profile = settings.active_profile
            status = box.row()
            status.label(text=f"Editing: {profile.name if profile else 'Committed Profile'}", icon='OUTLINER_OB_CURVE')

        # Profile actions stay together and prominent.
        row = box.row(align=True)
        row.operator("cpc.delete_last_part", text="Delete Last", icon='REMOVE')
        row.operator("cpc.clear_parts", text="Clear", icon='TRASH')

        if editing_profile_id:
            row = box.row(align=True)
            row.operator("cpc.commit_profile", text="Recommit Profile", icon='CHECKMARK')
            row.operator("cpc.cancel_profile_edit", text="Cancel", icon='CANCEL')
        else:
            box.operator("cpc.commit_profile", text="Commit Profile", icon='CHECKMARK')
            profile = settings.active_profile
            if profile and profile.get("cpc_recipe_json"):
                box.operator("cpc.reopen_profile", text="Edit Active Profile", icon='OUTLINER_OB_CURVE')

        if _disclosure(box, settings, "show_commit_advanced", "Commit / Utilities"):
            advanced = box.box()
            advanced.prop(settings, "preserve_bezier", text="Preserve Bézier")
            row = advanced.row(align=True)
            if settings.preserve_bezier:
                row.prop(settings, "merge_tolerance", text="Merge Tolerance")
            else:
                row.prop(settings, "sample_resolution", text="Resolution")
                row.prop(settings, "merge_tolerance", text="Merge")
            row = advanced.row(align=True)
            row.operator("cpc.show_parts", text="Show Parts", icon='HIDE_OFF')
            row.operator("cpc.use_selected_profile", text="Use Selected Profile", icon='EYEDROPPER')

    def _draw_user_profiles(self, layout, context, settings):
        box = layout.box()
        if not _section_header(box, settings, "show_user_profiles", "3. User Profiles", 'ASSET_MANAGER'):
            return

        source = context.object if context.object and context.object.type == 'CURVE' and not context.object.get("cpc_part") else settings.active_profile
        if source:
            preset_type, reason = user_profiles.profile_type_for_save(source)
            status = box.row()
            status.enabled = False
            label = "Save source: Editable CPC" if preset_type == 'PARAMETRIC' else "Save source: Static Curve"
            status.label(text=label, icon='MODIFIER' if preset_type == 'PARAMETRIC' else 'CURVE_DATA')
        box.operator("cpc.save_user_profile", text="Save Profile Preset", icon='ADD')

        box.separator()
        box.prop(settings, "user_profile_selected", text="Preset")
        try:
            box.template_icon_view(settings, "user_profile_selected", show_labels=True, scale=5.0, scale_popup=5.0)
        except TypeError:
            box.template_icon_view(settings, "user_profile_selected", show_labels=True)

        metadata = user_profiles.selected_metadata(settings)
        if metadata:
            info = box.row()
            info.enabled = False
            if metadata.get("profile_type") == 'PARAMETRIC':
                info.label(text="Editable CPC preset • recipe + geometry", icon='MODIFIER')
            else:
                info.label(text="Static Curve preset • geometry preserved", icon='CURVE_DATA')

        row = box.row(align=True)
        row.operator("cpc.load_user_profile", text="Load", icon='IMPORT')
        row.operator("cpc.refresh_user_profiles", text="Refresh", icon='FILE_REFRESH')
        row.operator("cpc.delete_user_profile", text="Delete", icon='TRASH')

        if _disclosure(box, settings, "show_user_profile_advanced", "Library Location"):
            advanced = box.box()
            advanced.prop(settings, "user_profile_library_path", text="Folder")
            hint = advanced.row()
            hint.enabled = False
            hint.label(text="Blank = Blender extension user storage / profiles")
            note = advanced.row()
            note.enabled = False
            note.label(text=".cpcprofile JSON is authoritative; PNG is a regenerable thumbnail")

    def _draw_sweep(self, layout, context, settings):
        box = layout.box()
        if not _section_header(box, settings, "show_sweep", "4. Sweep", 'MOD_SKIN'):
            return

        box.prop(settings, "active_profile", text="Profile")
        row = box.row(align=True)
        row.operator("cpc.flip_active_profile_x", text="Flip X")
        row.operator("cpc.flip_active_profile_y", text="Flip Y")
        row.operator("cpc.rotate_active_profile_90", text="Rotate 90°")

        adjust = box.box()
        adjust.label(text="Profile Transform", icon='ORIENTATION_LOCAL')
        adjust.prop(settings, "profile_adjust_uniform_scale", text="Uniform Scale")
        if settings.profile_adjust_uniform_scale:
            adjust.prop(settings, "profile_adjust_scale_x", text="Scale")
        else:
            row = adjust.row(align=True)
            row.prop(settings, "profile_adjust_scale_x", text="Scale X")
            row.prop(settings, "profile_adjust_scale_y", text="Scale Y")
        adjust.prop(settings, "profile_adjust_rotation", text="Rotation")

        obj = context.object
        if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
            box.operator("cpc.sweep_selected_edges", icon='OUTLINER_OB_CURVE')
        elif obj and obj.type == 'CURVE':
            box.operator("cpc.apply_profile_to_curve", icon='MOD_CURVE')
            box.operator("cpc.convert_sweep_to_mesh", icon='OUTLINER_OB_MESH')
        else:
            col = box.column()
            col.enabled = False
            col.label(text="Edit mesh edges or select a Curve to sweep")

        if _disclosure(box, settings, "show_sweep_advanced", "Sweep Settings"):
            advanced = box.box()
            row = advanced.row(align=True)
            row.prop(settings, "sweep_path_mode", text="Path")
            row.prop(settings, "fill_caps", text="Caps")
            smooth = advanced.row(align=True)
            smooth.prop(settings, "smooth_by_angle", text="Smooth")
            sub = smooth.row(align=True)
            sub.enabled = settings.smooth_by_angle
            sub.prop(settings, "smooth_angle", text="Angle")
            if settings.sweep_path_mode != '2D':
                advanced.prop(settings, "twist_mode", text="Twist")
            advanced.prop(settings, "path_resolution", text="Path Resolution")


_CLASSES = (CPC_PT_Main,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
