# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""UI Panel for the Slategray Blender Tools suite."""

import bpy  # type: ignore

# ------------------------------------------------------------------------------
# SIDEBAR UI
# ------------------------------------------------------------------------------


class SBT_PT_SidebarPanel(bpy.types.Panel):
    """Sidebar Panel."""

    bl_idname = "SBT_PT_SidebarPanel"
    bl_label = "Slategray Blender Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SLATE"

    def draw(self, context: bpy.types.Context) -> None:
        """Render UI buttons."""
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Mesh Tools")
        col.operator("object.sbt_apply_modifiers", icon="MODIFIER")

        col.separator()
        col.label(text="Rigging Tools")
        col.operator("object.sbt_apply_rest_pose", icon="POSE_HLT")


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register classes."""
    bpy.utils.register_class(SBT_PT_SidebarPanel)


def unregister() -> None:
    """Unregister classes."""
    bpy.utils.unregister_class(SBT_PT_SidebarPanel)
