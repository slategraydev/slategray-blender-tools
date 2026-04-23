# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Utilities for armature and rigging operations."""

import bpy  # type: ignore
import numpy as np

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------------------

EPSILON = 1e-6

# ------------------------------------------------------------------------------
# RIGGING UTILITIES
# ------------------------------------------------------------------------------


def apply_armature_rest_pose(context: bpy.types.Context, arm: bpy.types.Object) -> None:
    """Apply rest pose to the armature using a pure-data matrix approach."""
    if not arm or arm.type != "ARMATURE" or arm.library:
        return

    orig_active = context.view_layer.objects.active
    orig_mode = arm.mode

    try:
        context.view_layer.objects.active = arm
        if arm.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # 1. Force a dependency graph update to ensure all constraints are evaluated
        context.view_layer.update()

        # 2. Capture the exact evaluated visual matrices (in object space)
        bpy.ops.object.mode_set(mode="POSE")
        pose_matrices = {pb.name: pb.matrix.copy() for pb in arm.pose.bones}

        # 3. Switch to EDIT mode to overwrite the rest pose
        bpy.ops.object.mode_set(mode="EDIT")
        for eb in arm.data.edit_bones:
            if eb.name in pose_matrices:
                eb.matrix = pose_matrices[eb.name]

        # 4. Switch back to POSE mode to clear out local transform offsets
        bpy.ops.object.mode_set(mode="POSE")
        for pb in arm.pose.bones:
            pb.matrix_basis.identity()
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.rotation_axis_angle = (0, 0, 1, 0)
            pb.scale = (1, 1, 1)

        context.view_layer.update()

    except Exception as e:
        print(f"Error syncing rig '{arm.name}': {e}")
    finally:
        try:
            if arm.mode != orig_mode and orig_mode in {"OBJECT", "EDIT", "POSE"}:
                bpy.ops.object.mode_set(mode=orig_mode)
        except Exception:
            pass
        context.view_layer.objects.active = orig_active


def capture_vertex_group_weights(
    obj: bpy.types.Object, group_names: set[str]
) -> dict[str, np.ndarray]:
    """Capture weights for specified vertex groups using high-performance NumPy arrays."""
    weights_map = {}
    vert_count = len(obj.data.vertices)
    use_attr = hasattr(obj.data, "attributes")

    for name in group_names:
        vg = obj.vertex_groups.get(name)
        if not vg:
            continue

        weights = np.zeros(vert_count, dtype=np.float32)

        if use_attr:
            attr = obj.data.attributes.get(name)
            if attr and attr.domain == "POINT" and attr.data_type == "FLOAT":
                attr.data.foreach_get("value", weights)
                weights_map[name] = weights
                continue

        # Fallback for old Blender versions or if attribute lookup fails
        for v in obj.data.vertices:
            try:
                weights[v.index] = vg.weight(v.index)
            except RuntimeError:
                pass
        weights_map[name] = weights

    return weights_map


def apply_vertex_group_weights(obj: bpy.types.Object, weights_map: dict[str, np.ndarray]) -> None:
    """Apply captured weights to vertex groups using high-performance NumPy arrays."""
    vert_count = len(obj.data.vertices)
    use_attr = hasattr(obj.data, "attributes")

    for name, weights in weights_map.items():
        vg = obj.vertex_groups.get(name)
        if not vg:
            vg = obj.vertex_groups.new(name=name)

        if use_attr:
            attr = obj.data.attributes.get(name)
            if not attr:
                # Force attribute initialization by adding a single weight
                vg.add([0], 0.0, "REPLACE")
                attr = obj.data.attributes.get(name)

            if attr and attr.domain == "POINT" and attr.data_type == "FLOAT":
                attr.data.foreach_set("value", weights)
                continue

        # Fallback for old Blender versions
        for v in obj.data.vertices:
            vg.remove([v.index])

        for v_idx in range(vert_count):
            if weights[v_idx] > EPSILON:
                vg.add([v_idx], float(weights[v_idx]), "REPLACE")
