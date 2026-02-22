# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""High-performance utilities for baking mesh data and modifiers."""

from typing import Any

import bpy  # type: ignore
import numpy as np

SHAPE_ATTRIBUTES = (
    "interpolation",
    "mute",
    "name",
    "slider_max",
    "slider_min",
    "value",
    "vertex_group",
)


def extract_mesh_data(
    ob: bpy.types.Object,
    context: bpy.types.Context,
) -> tuple[int, list[np.ndarray]] | tuple[None, str]:
    """Capture vertex coordinates across all shape keys using NumPy."""
    coords_collection: list[np.ndarray] = []
    depsgraph = context.evaluated_depsgraph_get()
    key_blocks = ob.data.shape_keys.key_blocks
    total_shapes = len(key_blocks)

    reference_vert_count = -1
    coord_buffer = None

    # Performance Optimization: Mute all shapes once to isolate states
    original_state = [(kb.value, kb.mute) for kb in key_blocks]
    for kb in key_blocks:
        kb.mute, kb.value = True, 0.0

    try:
        for i in range(total_shapes):
            kb = key_blocks[i]
            kb.mute, kb.value = False, 1.0

            ob.update_tag()
            depsgraph.update()

            eval_obj = ob.evaluated_get(depsgraph)
            temp_mesh = eval_obj.to_mesh()

            current_count = len(temp_mesh.vertices)
            if i == 0:
                reference_vert_count = current_count
                coord_buffer = np.empty(reference_vert_count * 3, dtype=np.float32)
            elif current_count != reference_vert_count:
                eval_obj.to_mesh_clear()
                return None, "Topology mismatch detected."

            if coord_buffer is not None:
                temp_mesh.vertices.foreach_get("co", coord_buffer)
                coords_collection.append(coord_buffer.copy())

            eval_obj.to_mesh_clear()
            kb.mute, kb.value = True, 0.0
    finally:
        # Always restore original state
        for idx, (val, mute) in enumerate(original_state):
            key_blocks[idx].value, key_blocks[idx].mute = val, mute

    return reference_vert_count, coords_collection


def get_modifier_snapshot(mod: bpy.types.Modifier) -> dict[str, Any]:
    """Capture all properties of a modifier for restoration."""
    snapshot = {"name": mod.name, "type": mod.type, "show_viewport": mod.show_viewport}
    for prop in mod.bl_rna.properties:
        if not prop.is_readonly and prop.identifier not in {"name", "type"}:
            snapshot[prop.identifier] = getattr(mod, prop.identifier)
    return snapshot


def restore_object(
    ob: bpy.types.Object,
    metadata: list[dict],
    baked_coords: list[np.ndarray],
    stack_snapshots: list[dict],
    selected_mods: list[str],
    keep_armatures: bool,
) -> None:
    """Wipe object and reconstruct mesh/modifiers from snapshots."""
    # 1. Clear Data
    if ob.data.shape_keys:
        for kb in reversed(ob.data.shape_keys.key_blocks):
            ob.shape_key_remove(kb)
    ob.modifiers.clear()

    # 2. Restore Geometry
    ob.data.vertices.foreach_set("co", baked_coords[0])

    # 3. Restore Stack
    sel_set = set(selected_mods)
    for snap in stack_snapshots:
        is_baked = snap["name"] in sel_set
        is_arm = snap["type"] == "ARMATURE"
        hidden = not snap["show_viewport"]

        # Keep if: not selected to bake OR hidden OR it's an armature and we're syncing rig
        if (not is_baked) or hidden or (is_arm and keep_armatures):
            new_mod = ob.modifiers.new(name=snap["name"], type=snap["type"])
            for key, val in snap.items():
                if key not in {"name", "type"}:
                    try:
                        setattr(new_mod, key, val)
                    except Exception:
                        pass

    # 4. Restore Shape Keys
    for i, meta in enumerate(metadata):
        kb = ob.shape_key_add(name=meta["name"], from_mix=False)
        kb.data.foreach_set("co", baked_coords[i])
        for attr in SHAPE_ATTRIBUTES:
            if attr != "name":
                setattr(kb, attr, meta[attr])

    if ob.data.shape_keys:
        blocks = ob.data.shape_keys.key_blocks
        for i, meta in enumerate(metadata):
            rel = meta["rel"]
            if rel in blocks:
                blocks[i].relative_key = blocks[rel]


def apply_armature_rest_pose(context: bpy.types.Context, arm: bpy.types.Object) -> None:
    """Aggressively apply rest pose to the armature."""
    if not arm or arm.type != "ARMATURE" or arm.library:
        return

    was_hidden = arm.hide_viewport
    arm.hide_viewport = False

    orig_active = context.view_layer.objects.active
    context.view_layer.objects.active = arm
    orig_mode = arm.mode

    try:
        if arm.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.armature_apply()
    except Exception as e:
        print(f"Apply Modifiers: Error syncing rig '{arm.name}': {e}")
    finally:
        try:
            if arm.mode != orig_mode:
                bpy.ops.object.mode_set(mode=orig_mode)
        except Exception:
            pass
        context.view_layer.objects.active = orig_active
        arm.hide_viewport = was_hidden
