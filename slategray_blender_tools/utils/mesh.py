# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""High-performance data pipelines for mesh snapshots and baking."""

from collections.abc import Callable
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
    """Capture vertex coordinates across all shape keys using cache-aligned buffers."""
    coords_collection: list[np.ndarray] = []
    depsgraph = context.evaluated_depsgraph_get()

    if not ob.data.shape_keys:
        ob.update_tag()
        depsgraph.update()
        eval_obj = ob.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()
        vert_count = len(temp_mesh.vertices)
        coord_buffer = np.empty(vert_count * 3, dtype=np.float32, order="C")
        temp_mesh.vertices.foreach_get("co", coord_buffer)
        coords_collection.append(coord_buffer.reshape(vert_count, 3))
        eval_obj.to_mesh_clear()
        return vert_count, coords_collection

    key_blocks = ob.data.shape_keys.key_blocks
    total_shapes = len(key_blocks)
    reference_vert_count = -1

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
            elif current_count != reference_vert_count:
                eval_obj.to_mesh_clear()
                return None, "Topology mismatch detected."

            coord_buffer = np.empty(reference_vert_count * 3, dtype=np.float32, order="C")
            temp_mesh.vertices.foreach_get("co", coord_buffer)
            coords_collection.append(coord_buffer.reshape(reference_vert_count, 3))

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
) -> tuple[list[dict[str, Any]], list[np.ndarray]] | tuple[None, None]:
    """Capture shape key metadata and vertex coordinates for an object."""
    if ob.data.shape_keys:
        meta: list[dict[str, Any]] = [
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
        res = extract_mesh_data(ob, context)
        if res[0] is None:
            return None, None
        _, coords = res

    return meta, coords


# ------------------------------------------------------------------------------
# OBJECT RECONSTRUCTION & PIPELINE
# ------------------------------------------------------------------------------


def _reconstruct_modifiers(
    ob: bpy.types.Object,
    stack_snapshots: list[dict],
    selected_mods: list[str],
    keep_armatures: bool,
) -> None:
    """Helper for restore_object: re-adds non-baked or preserved modifiers."""
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


def _reconstruct_shape_keys(
    ob: bpy.types.Object,
    metadata: list[dict],
    baked_coords: list[np.ndarray],
) -> None:
    """Helper for restore_object: restores all shape keys from metadata."""
    for i, meta in enumerate(metadata):
        kb = ob.shape_key_add(name=meta["name"], from_mix=False)
        kb.data.foreach_set("co", baked_coords[i].ravel())
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
    if ob.data.shape_keys:
        for kb in reversed(ob.data.shape_keys.key_blocks):
            ob.shape_key_remove(kb)
    ob.modifiers.clear()

    ob.data.vertices.foreach_set("co", baked_coords[0].ravel())

    _reconstruct_modifiers(ob, stack_snapshots, selected_mods, keep_armatures)
    _reconstruct_shape_keys(ob, metadata, baked_coords)


def bake_mesh_operation(
    context: bpy.types.Context,
    ob: bpy.types.Object,
    selected_mods: list[str],
    keep_armatures: bool,
    pre_restore_callback: Callable | None = None,
) -> bool:
    """Standardized pipeline for baking modifiers while preserving shape keys."""
    snaps = [get_modifier_snapshot(m) for m in ob.modifiers]
    meta, coords = capture_mesh_snapshot(ob, context)
    if meta is None or coords is None:
        return False

    if pre_restore_callback:
        pre_restore_callback()

    restore_object(ob, meta, coords, snaps, selected_mods, keep_armatures)
    return True
