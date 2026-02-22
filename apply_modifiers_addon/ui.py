# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""UI Panel for the Apply Modifiers addon."""

import bpy  # type: ignore

from .operators import MSK_OT_ApplyModifiers, MSK_OT_ApplyRestPose


class MSK_PT_SidebarPanel(bpy.types.Panel):
    """Sidebar Panel."""

    bl_idname = "MSK_PT_SidebarPanel"
    bl_label = "Apply Modifiers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context: bpy.types.Context) -> None:
        """Render UI buttons."""
        layout = self.layout
        layout.operator(MSK_OT_ApplyModifiers.bl_idname, icon="RECOVER_LAST")
        layout.operator(MSK_OT_ApplyRestPose.bl_idname, icon="ARMATURE_DATA")
