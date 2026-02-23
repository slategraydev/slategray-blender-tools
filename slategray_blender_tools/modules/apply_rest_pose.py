# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Operator for baking pose and updating rest pose."""

import time

import bpy  # type: ignore

from ..utils import apply_armature_rest_pose, bake_mesh_operation

# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


class SBT_OT_ApplyRestPose(bpy.types.Operator):
    """Bake pose, update rest pose, and re-apply modifiers."""

    bl_idname = "object.sbt_apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Perform one-click rig and mesh sync using the centralized bake pipeline."""
        timer_start = time.time()
        obs = [o for o in context.selected_objects if o.type == "MESH"]
        if not obs:
            self.report({"WARNING"}, "No mesh objects selected.")
            return {"CANCELLED"}

        orig_active = context.view_layer.objects.active
        orig_selected = list(context.selected_objects)

        armatures = set()
        for ob in obs:
            for m in ob.modifiers:
                if m.type == "ARMATURE" and m.object:
                    armatures.add(m.object)

        def sync_callback():
            """Internal callback to sync rigs between snapshots and restoration."""
            for arm in armatures:
                apply_armature_rest_pose(context, arm)
            context.view_layer.update()

        for ob in obs:
            context.view_layer.objects.active = ob
            sel_mods = [m.name for m in ob.modifiers if m.show_viewport]
            bake_mesh_operation(context, ob, sel_mods, True, sync_callback)

        context.view_layer.objects.active = orig_active
        for o in orig_selected:
            o.select_set(True)

        self.report({"INFO"}, "Rest pose applied to rig and meshes.")
        print(f"Apply Rest Pose: Finished in {time.time() - timer_start:.4f}s")
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
