# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Operator for removing empty vertex groups from selected meshes."""

import time

import bpy  # type: ignore

from ..utils import get_empty_vertex_group_indices

# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


class SBT_OT_CleanVertexGroups(bpy.types.Operator):
    """Remove vertex groups that have no vertices assigned (One-Click)."""

    bl_idname = "object.sbt_clean_vertex_groups"
    bl_label = "Clean Vertex Groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Identify and remove empty vertex groups from selection."""
        timer_start = time.time()
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]

        if not selected_meshes:
            self.report({"WARNING"}, "No mesh objects selected.")
            return {"CANCELLED"}

        total_removed = 0
        for obj in selected_meshes:
            empty_indices = get_empty_vertex_group_indices(obj)
            to_remove = [vg for vg in obj.vertex_groups if vg.index in empty_indices]

            for vg in sorted(to_remove, key=lambda x: x.index, reverse=True):
                obj.vertex_groups.remove(vg)
                total_removed += 1

        if total_removed == 0:
            self.report({"INFO"}, "No empty vertex groups found.")
        else:
            self.report({"INFO"}, f"Cleaned {total_removed} empty vertex groups.")

        print(f"Clean Vertex Groups: Finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register class."""
    bpy.utils.register_class(SBT_OT_CleanVertexGroups)


def unregister() -> None:
    """Unregister class."""
    bpy.utils.unregister_class(SBT_OT_CleanVertexGroups)
