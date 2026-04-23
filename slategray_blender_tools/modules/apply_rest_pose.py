# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Operator for baking modifiers, applying rest pose, and re-adding armatures."""

import time
from collections.abc import Callable
from typing import Any

import bpy  # type: ignore

from ..utils import (
    apply_armature_rest_pose,
    bake_mesh_operation,
    force_object_mode,
    get_modifier_snapshot,
)

ModifierSnapshot = dict[str, Any]
MeshModifierRestore = tuple[bpy.types.Object, list[ModifierSnapshot]]

# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


def _collect_selected_armatures(context: bpy.types.Context) -> set[bpy.types.Object]:
    """Collect explicitly selected armatures."""
    return {ob for ob in context.selected_objects if ob.type == "ARMATURE"}


def _collect_armatures(meshes: list[bpy.types.Object]) -> set[bpy.types.Object]:
    """Collect unique armatures driving the selected meshes."""
    armatures = set()
    for ob in meshes:
        for mod in ob.modifiers:
            if mod.type == "ARMATURE" and mod.object:
                armatures.add(mod.object)
    return armatures


def _find_meshes_for_armatures(
    context: bpy.types.Context,
    armatures: set[bpy.types.Object],
) -> list[bpy.types.Object]:
    """Find every mesh in the scene driven by the given armatures."""
    if not armatures:
        return []

    meshes = []
    for ob in context.scene.objects:
        if ob.type != "MESH":
            continue
        if any(mod.type == "ARMATURE" and mod.object in armatures for mod in ob.modifiers):
            meshes.append(ob)
    return sorted(meshes, key=lambda ob: ob.name)


def _resolve_targets(
    context: bpy.types.Context,
    include_all_meshes: bool,
) -> tuple[list[bpy.types.Object], set[bpy.types.Object]]:
    """Resolve target meshes and armatures from the current selection."""
    selected_meshes = [ob for ob in context.selected_objects if ob.type == "MESH"]
    selected_armatures = _collect_selected_armatures(context)

    if include_all_meshes:
        armatures = selected_armatures or _collect_armatures(selected_meshes)
        meshes = _find_meshes_for_armatures(context, armatures)
        return meshes, armatures

    if selected_meshes:
        armatures = _collect_armatures(selected_meshes)
        meshes = [
            ob
            for ob in selected_meshes
            if any(mod.type == "ARMATURE" and mod.object in armatures for mod in ob.modifiers)
        ]
        return meshes, armatures

    return _find_meshes_for_armatures(context, selected_armatures), selected_armatures


def _collect_modifier_snapshots(
    meshes: list[bpy.types.Object],
) -> list[MeshModifierRestore]:
    """Snapshot full modifier stacks for later reconstruction."""
    snapshots = []
    for ob in meshes:
        stack_snapshots = [get_modifier_snapshot(mod) for mod in ob.modifiers]
        if stack_snapshots:
            snapshots.append((ob, stack_snapshots))
    return snapshots


def _remove_non_armature_modifiers(restores: list[MeshModifierRestore]) -> None:
    """Temporarily remove all non-armature modifiers before armature baking."""
    for ob, _stack_snapshots in restores:
        for mod in list(reversed(ob.modifiers)):
            if mod.type != "ARMATURE":
                ob.modifiers.remove(mod)


def _restore_modifier_subset(
    restores: list[MeshModifierRestore],
    include_types: set[str],
) -> None:
    """Rebuild a subset of modifiers in their original stack order."""
    for ob, stack_snapshots in restores:
        for index, snap in enumerate(stack_snapshots):
            if snap["type"] not in include_types:
                continue

            if ob.modifiers.get(snap["name"]):
                continue

            new_mod = ob.modifiers.new(name=snap["name"], type=snap["type"])
            for key, val in snap.items():
                if key in {"name", "type"}:
                    continue
                try:
                    setattr(new_mod, key, val)
                except Exception:
                    pass

            target_index = sum(
                1 for prev in stack_snapshots[:index] if ob.modifiers.get(prev["name"])
            )
            ob.modifiers.move(len(ob.modifiers) - 1, min(target_index, len(ob.modifiers) - 1))


def _apply_armature_modifiers(
    context: bpy.types.Context,
    meshes: list[bpy.types.Object],
    report: Callable[[set[str], str], None],
) -> list[bpy.types.Object]:
    """Apply all armature modifiers on each mesh using the shared bake utility."""
    baked_meshes = []
    for ob in meshes:
        selected_mods = [mod.name for mod in ob.modifiers if mod.type == "ARMATURE"]
        if not selected_mods:
            report({"WARNING"}, f"No armature modifiers to apply on '{ob.name}'.")
            continue

        context.view_layer.objects.active = ob
        if bake_mesh_operation(context, ob, selected_mods, False):
            baked_meshes.append(ob)
        else:
            report({"WARNING"}, f"Failed to apply armature modifiers on '{ob.name}'.")
    return baked_meshes


def _apply_rest_pose_to_armatures(
    context: bpy.types.Context, armatures: set[bpy.types.Object]
) -> None:
    """Apply current pose as rest pose on each affected armature."""
    for arm in armatures:
        apply_armature_rest_pose(context, arm)
    context.view_layer.update()


def _restore_selection(
    context: bpy.types.Context,
    active_object: bpy.types.Object | None,
    selected_objects: list[bpy.types.Object],
) -> None:
    """Restore the user's selection and active object."""
    for ob in context.selected_objects:
        ob.select_set(False)
    for ob in selected_objects:
        ob.select_set(True)
    context.view_layer.objects.active = active_object


def _restore_mode(active_object: bpy.types.Object | None, mode: str | None) -> None:
    """Restore the previous interaction mode when Blender allows it."""
    if not active_object or not mode or mode == "OBJECT":
        return

    try:
        bpy.ops.object.mode_set(mode=mode)
    except Exception:
        pass


def _execute_apply_rest_pose(
    operator: bpy.types.Operator,
    context: bpy.types.Context,
    include_all_meshes: bool,
) -> set[str]:
    """Run the rest-pose workflow for the resolved targets."""
    timer_start = time.time()
    meshes, armatures = _resolve_targets(context, include_all_meshes)

    if not meshes:
        operator.report({"WARNING"}, "No driven mesh objects found.")
        return {"CANCELLED"}
    if not armatures:
        operator.report({"WARNING"}, "No armatures found for the target meshes.")
        return {"CANCELLED"}

    orig_active = context.view_layer.objects.active
    orig_selected = list(context.selected_objects)
    orig_mode = orig_active.mode if orig_active else None
    force_object_mode()

    try:
        modifier_restores = _collect_modifier_snapshots(meshes)
        _remove_non_armature_modifiers(modifier_restores)
        baked_meshes = _apply_armature_modifiers(context, meshes, operator.report)

        if not baked_meshes:
            operator.report({"WARNING"}, "No meshes were baked successfully.")
            return {"CANCELLED"}

        _apply_rest_pose_to_armatures(context, armatures)
        _restore_modifier_subset(modifier_restores, {"ARMATURE"})
        _restore_modifier_subset(
            modifier_restores,
            {
                snap["type"]
                for _ob, snaps in modifier_restores
                for snap in snaps
                if snap["type"] != "ARMATURE"
            },
        )

        operator.report({"INFO"}, f"Rest pose applied to {len(baked_meshes)} mesh(es).")
        print(f"Apply Rest Pose: Finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}
    finally:
        _restore_selection(context, orig_active, orig_selected)
        _restore_mode(orig_active, orig_mode)


class SBT_OT_ApplyRestPose(bpy.types.Operator):
    """Bake pose, update rest pose, and re-apply modifiers."""

    bl_idname = "object.sbt_apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Apply rest pose to the selected meshes or selected armature meshes."""
        return _execute_apply_rest_pose(self, context, include_all_meshes=False)


class SBT_OT_ApplyRestPoseAll(bpy.types.Operator):
    """Apply rest pose to every mesh driven by the resolved armature selection."""

    bl_idname = "object.sbt_apply_rest_pose_all"
    bl_label = "Apply Rest Pose to All"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Apply rest pose to all scene meshes driven by the target armature(s)."""
        return _execute_apply_rest_pose(self, context, include_all_meshes=True)


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register class."""
    bpy.utils.register_class(SBT_OT_ApplyRestPose)
    bpy.utils.register_class(SBT_OT_ApplyRestPoseAll)


def unregister() -> None:
    """Unregister class."""
    bpy.utils.unregister_class(SBT_OT_ApplyRestPoseAll)
    bpy.utils.unregister_class(SBT_OT_ApplyRestPose)
