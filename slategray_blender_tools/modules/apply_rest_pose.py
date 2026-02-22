# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Operator for baking pose and updating rest pose."""

import time

import bpy  # type: ignore

from ..utils import (
    apply_armature_rest_pose,
    capture_mesh_snapshot,
    get_modifier_snapshot,
    restore_object,
)

# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


class SBT_OT_ApplyRestPose(bpy.types.Operator):
    """Bake pose, update rest pose, and re-apply modifiers."""

    bl_idname = "object.sbt_apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Perform one-click rig and mesh sync."""
        timer_start = time.time()
        obs = [o for o in context.selected_objects if o.type == "MESH"]
        if not obs:
            self.report({"WARNING"}, "No mesh objects selected.")
            return {"CANCELLED"}

        orig_active = context.view_layer.objects.active
        orig_selected = list(context.selected_objects)

        data_map = {}
        armatures = set()
        for ob in obs:
            snaps = [get_modifier_snapshot(m) for m in ob.modifiers]
            sel_mods = [m.name for m in ob.modifiers if m.show_viewport]
            for m in ob.modifiers:
                if m.type == "ARMATURE" and m.object:
                    armatures.add(m.object)

            context.view_layer.objects.active = ob
            meta, coords = capture_mesh_snapshot(ob, context)
            if meta is None or coords is None:
                continue
            data_map[ob.name] = (meta, coords, snaps, sel_mods)

        for arm in armatures:
            apply_armature_rest_pose(context, arm)
        context.view_layer.update()

        for name, (meta, coords, snaps, sel_mods) in data_map.items():
            ob = bpy.data.objects.get(name)
            if ob:
                restore_object(ob, meta, coords, snaps, sel_mods, True)

        context.view_layer.objects.active = orig_active
        for o in orig_selected:
            o.select_set(True)

        print(f"Apply Rest Pose: Sync finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register class."""
    bpy.utils.register_class(SBT_OT_ApplyRestPose)


def unregister() -> None:
    """Unregister class."""
    bpy.utils.unregister_class(SBT_OT_ApplyRestPose)
