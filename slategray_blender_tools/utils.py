# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""High-performance utilities for baking mesh data and modifiers."""

from typing import Any

import bpy  # type: ignore
import numpy as np

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------------------

SHAPE_ATTRIBUTES = (
    "interpolation",
    "mute",
    "name",
    "slider_max",
    "slider_min",
    "value",
    "vertex_group",
)


# ------------------------------------------------------------------------------
# DATA EXTRACTION
# ------------------------------------------------------------------------------


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


def capture_mesh_snapshot(
    ob: bpy.types.Object,
    context: bpy.types.Context,
) -> tuple[list[dict], list[np.ndarray]] | tuple[None, None]:
    """Capture shape key metadata and vertex coordinates for an object."""
    if ob.data.shape_keys:
        meta = [
            {
                **{a: getattr(kb, a) for a in SHAPE_ATTRIBUTES},
                "rel": kb.relative_key.name if kb.relative_key else kb.name,
            }
            for kb in ob.data.shape_keys.key_blocks
        ]
        res = extract_mesh_data(ob, context)
        if res[0] is None:
            return None, None
        _, coords = res
    else:
        meta = []
        deps = context.evaluated_depsgraph_get()
        ob.update_tag()
        deps.update()
        eval_ob = ob.evaluated_get(deps)
        temp = eval_ob.to_mesh()
        buf = np.empty(len(temp.vertices) * 3, dtype=np.float32)
        temp.vertices.foreach_get("co", buf)
        coords = [buf]
        eval_ob.to_mesh_clear()

    return meta, coords


# ------------------------------------------------------------------------------
# OBJECT RECONSTRUCTION
# ------------------------------------------------------------------------------


def _clear_object_data(ob: bpy.types.Object) -> None:
    """Wipe all shape keys and modifiers from the object."""
    if ob.data.shape_keys:
        for kb in reversed(ob.data.shape_keys.key_blocks):
            ob.shape_key_remove(kb)
    ob.modifiers.clear()


def _restore_modifier_stack(
    ob: bpy.types.Object,
    stack_snapshots: list[dict],
    selected_mods: list[str],
    keep_armatures: bool,
) -> None:
    """Reconstruct the modifier stack from snapshots."""
    sel_set = set(selected_mods)
    for snap in stack_snapshots:
        is_baked = snap["name"] in sel_set
        is_arm = snap["type"] == "ARMATURE"
        hidden = not snap["show_viewport"]

        if (not is_baked) or hidden or (is_arm and keep_armatures):
            new_mod = ob.modifiers.new(name=snap["name"], type=snap["type"])
            for key, val in snap.items():
                if key not in {"name", "type"}:
                    try:
                        setattr(new_mod, key, val)
                    except Exception:
                        pass


def _restore_shape_keys(
    ob: bpy.types.Object,
    metadata: list[dict],
    baked_coords: list[np.ndarray],
) -> None:
    """Reconstruct shape keys from snapshots."""
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


def restore_object(
    ob: bpy.types.Object,
    metadata: list[dict],
    baked_coords: list[np.ndarray],
    stack_snapshots: list[dict],
    selected_mods: list[str],
    keep_armatures: bool,
) -> None:
    """Wipe object and reconstruct mesh/modifiers from snapshots."""
    _clear_object_data(ob)
    ob.data.vertices.foreach_set("co", baked_coords[0])
    _restore_modifier_stack(ob, stack_snapshots, selected_mods, keep_armatures)
    _restore_shape_keys(ob, metadata, baked_coords)


# ------------------------------------------------------------------------------
# ARMATURE OPERATIONS
# ------------------------------------------------------------------------------


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
