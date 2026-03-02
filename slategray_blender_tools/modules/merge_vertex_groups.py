# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Module for merging multiple vertex groups into one using Weight Mix logic."""

import time

import bpy  # type: ignore
from bpy.props import EnumProperty, IntProperty, StringProperty  # type: ignore

from ..utils import force_object_mode

# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


class SBT_OT_MergeVertexGroups(bpy.types.Operator):
    """Merge multiple vertex groups into one using iterative mix modifiers."""

    bl_idname = "object.sbt_merge_vertex_groups"
    bl_label = "Merge Vertex Groups"
    bl_options = {"REGISTER", "UNDO"}

    def _merge_group(self, context, obj, target_name, src_name, mix_mode, mix_set, delete):
        """Apply weight mix modifier for a single group and optionally delete it."""
        if src_name == target_name or src_name not in obj.vertex_groups:
            return False

        # Add and configure modifier
        mod = obj.modifiers.new(name="SBT_MERGE_MIX", type="VERTEX_WEIGHT_MIX")
        mod.vertex_group_a = target_name
        mod.vertex_group_b = src_name
        mod.mix_mode = mix_mode
        mod.mix_set = mix_set

        # Force evaluation and apply
        context.view_layer.update()
        bpy.ops.object.modifier_apply(modifier=mod.name)

        if delete:
            vg = obj.vertex_groups.get(src_name)
            if vg:
                obj.vertex_groups.remove(vg)
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Perform the iterative merge."""
        timer_start = time.time()
        settings = context.scene.sbt_merge_vgs
        obj = context.active_object

        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "No active mesh object.")
            return {"CANCELLED"}

        if not settings.target_group:
            self.report({"WARNING"}, "No target group specified.")
            return {"CANCELLED"}

        if not settings.sources:
            self.report({"WARNING"}, "No source groups selected.")
            return {"CANCELLED"}

        force_object_mode()

        # Ensure target group exists
        if settings.target_group not in obj.vertex_groups:
            obj.vertex_groups.new(name=settings.target_group)

        count = 0
        for item in settings.sources:
            if self._merge_group(
                context,
                obj,
                settings.target_group,
                item.name,
                settings.mix_mode,
                settings.mix_set,
                settings.delete_sources,
            ):
                count += 1

        if settings.delete_sources:
            settings.sources.clear()

        self.report({"INFO"}, f"Merged {count} groups into '{settings.target_group}'.")
        print(f"Merge Vertex Groups: Finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}


# ------------------------------------------------------------------------------
# UI CONTROL OPERATORS
# ------------------------------------------------------------------------------


class SBT_OT_MergeVGsUI(bpy.types.Operator):
    """Manage Merge Vertex Groups UI state."""

    bl_idname = "object.sbt_merge_vgs_ui"
    bl_label = "Merge VGs UI"
    bl_options = {"INTERNAL"}

    action: EnumProperty(  # type: ignore
        items=[
            ("INVERT_SOURCES", "Invert Selection", ""),
            ("CLEAR_SOURCES", "Clear List", ""),
            ("REMOVE_SOURCE", "Remove Item", ""),
            ("SET_TARGET", "Set Target", ""),
        ]
    )
    index: IntProperty(default=-1)  # type: ignore
    value: StringProperty()  # type: ignore

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Perform UI action."""
        settings = context.scene.sbt_merge_vgs
        obj = context.active_object
        a = self.action

        if a == "SET_TARGET":
            settings.target_group = self.value
        elif a == "CLEAR_SOURCES":
            settings.sources.clear()
        elif a == "REMOVE_SOURCE" and self.index >= 0:
            settings.sources.remove(self.index)
        elif a == "INVERT_SOURCES" and obj:
            existing = {i.name for i in settings.sources}
            all_vgs = [vg.name for vg in obj.vertex_groups if vg.name != settings.target_group]
            settings.sources.clear()
            for name in all_vgs:
                if name not in existing:
                    settings.sources.add().name = name

        return {"FINISHED"}


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register classes."""
    bpy.utils.register_class(SBT_OT_MergeVertexGroups)
    bpy.utils.register_class(SBT_OT_MergeVGsUI)


def unregister() -> None:
    """Unregister classes."""
    bpy.utils.unregister_class(SBT_OT_MergeVGsUI)
    bpy.utils.unregister_class(SBT_OT_MergeVertexGroups)
