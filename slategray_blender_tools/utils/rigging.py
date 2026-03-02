# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Utilities for armature and rigging operations."""

import bpy  # type: ignore

# ------------------------------------------------------------------------------
# RIGGING UTILITIES
# ------------------------------------------------------------------------------


def apply_armature_rest_pose(context: bpy.types.Context, arm: bpy.types.Object) -> None:
    """Apply rest pose to the armature."""
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
        print(f"Error syncing rig '{arm.name}': {e}")
    finally:
        try:
            if arm.mode != orig_mode:
                bpy.ops.object.mode_set(mode=orig_mode)
        except Exception:
            pass
        context.view_layer.objects.active = orig_active
        arm.hide_viewport = was_hidden


def capture_vertex_group_weights(
    obj: bpy.types.Object, group_names: set[str]
) -> dict[str, list[tuple[int, float]]]:
    """Capture weights for specified vertex groups."""
    weights_map = {}
    for name in group_names:
        vg = obj.vertex_groups.get(name)
        if not vg:
            continue

        weights = []
        for v in obj.data.vertices:
            try:
                w = vg.weight(v.index)
                weights.append((v.index, w))
            except RuntimeError:
                pass
        weights_map[name] = weights
    return weights_map


def apply_vertex_group_weights(
    obj: bpy.types.Object, weights_map: dict[str, list[tuple[int, float]]]
) -> None:
    """Apply captured weights to vertex groups, clearing existing weights first."""
    for name, weights in weights_map.items():
        vg = obj.vertex_groups.get(name)
        if not vg:
            vg = obj.vertex_groups.new(name=name)

        # Clear existing weights in this group
        for v in obj.data.vertices:
            vg.remove([v.index])

        # Apply saved weights
        for v_idx, w in weights:
            vg.add([v_idx], w, "REPLACE")
