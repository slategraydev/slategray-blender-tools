# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray). All rights reserved.
# ------------------------------------------------------------------------------

"""UI Panel for the Slategray Blender Tools suite."""

import bpy  # type: ignore

# ~~~~~~~~~~~~~~~~
# SIDEBAR UI
# ~~~~~~~~~~~~~~~~
# Primary interaction panel in the 3D View Sidebar.


class SBT_PT_SidebarPanel(bpy.types.Panel):
    """Main Sidebar Panel."""

    bl_idname = "SBT_PT_SidebarPanel"
    bl_label = "Slategray Blender Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SLATE"

    def draw(self, context: bpy.types.Context) -> None:
        """Render UI components."""
        layout = self.layout

        # Mesh Tools Section
        col = layout.column(align=True)
        col.label(text="Mesh Tools")
        col.operator("object.sbt_apply_modifiers", icon="MODIFIER")
        col.operator("object.sbt_clean_vertex_groups", icon="GROUP_VERTEX")

        # Rigging Tools Section
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Rigging Tools")
        col.operator("object.sbt_apply_rest_pose", icon="POSE_HLT")
        col.operator("object.sbt_apply_rest_pose_all", icon="ARMATURE_DATA")

        # Scene Hygiene Section
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Scene Hygiene")
        col.operator("object.sbt_purge_unused_data", icon="TRASH")


class SBT_PT_ShapeKeyTransfer(bpy.types.Panel):
    """Sub-panel for Shape Key Transfer."""

    bl_parent_id = "SBT_PT_SidebarPanel"
    bl_idname = "SBT_PT_ShapeKeyTransfer"
    bl_label = "Shape Key Transfer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SLATE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Render settings."""
        layout = self.layout
        settings = context.scene.sbt_shape_key_transfer

        # Stacked Object Selection
        col = layout.column(align=True)
        col.prop(settings, "source_obj", text="Base", icon="OBJECT_DATA")
        col.prop(settings, "target_obj", text="Target", icon="OBJECT_DATA")

        col.separator()
        op = col.operator(
            "object.sbt_shape_key_transfer_ui", text="Auto-Detect Selection", icon="NODE_SEL"
        )
        op.action = "AUTO_DETECT"

        layout.separator()
        layout.prop(settings, "smooth_iterations")

        # Mask List (Vertical)
        layout.separator()
        layout.label(text="Mask to Groups (Target)", icon="GROUP_VERTEX")
        layout.prop(settings, "target_picker", text="")

        box = layout.box()
        if not settings.target_ignored:
            box.label(text="Entire Mesh", icon="MESH_DATA")
        else:
            for i, item in enumerate(settings.target_ignored):
                row = box.row(align=True)
                row.label(text=item.name)
                op = row.operator("object.sbt_shape_key_transfer_ui", icon="X", text="")
                op.action = "REMOVE_TARGET"
                op.index = i

        row = layout.row(align=True)
        row.operator("object.sbt_shape_key_transfer_ui", text="Invert").action = "INVERT_TARGET"
        row.operator("object.sbt_shape_key_transfer_ui", text="Clear").action = "CLEAR_TARGET"

        layout.separator()
        layout.operator("object.sbt_transfer_shape_keys", icon="SHAPEKEY_DATA")


class SBT_PT_MergeVertexGroups(bpy.types.Panel):
    """Sub-panel for Merging Vertex Groups."""

    bl_parent_id = "SBT_PT_SidebarPanel"
    bl_idname = "SBT_PT_MergeVertexGroups"
    bl_label = "Merge Vertex Groups"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SLATE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Render settings."""
        layout = self.layout
        settings = context.scene.sbt_merge_vgs

        # Target Selection
        col = layout.column(align=True)
        col.label(text="Target Group", icon="GROUP_VERTEX")
        row = col.row(align=True)
        row.prop(settings, "target_group", text="")
        row.prop(settings, "target_picker", text="", icon="GROUP_VERTEX")

        layout.separator()
        layout.prop(settings, "mix_mode")
        layout.prop(settings, "mix_set")
        layout.prop(settings, "delete_sources", text="Delete Source Groups", icon="TRASH")

        # Source List (Vertical Stack)
        layout.separator()
        layout.label(text="Source Groups to Merge", icon="GROUP_VERTEX")
        layout.prop(settings, "source_picker", text="")

        box = layout.box()
        if not settings.sources:
            box.label(text="No sources selected")
        else:
            for i, item in enumerate(settings.sources):
                row = box.row(align=True)
                row.label(text=item.name)
                op = row.operator("object.sbt_merge_vgs_ui", icon="X", text="")
                op.action = "REMOVE_SOURCE"
                op.index = i

        row = layout.row(align=True)
        row.operator("object.sbt_merge_vgs_ui", text="Invert").action = "INVERT_SOURCES"
        row.operator("object.sbt_merge_vgs_ui", text="Clear").action = "CLEAR_SOURCES"

        layout.separator()
        layout.operator("object.sbt_merge_vertex_groups", icon="AUTOMERGE_ON")


# ~~~~~~~~~~~~~~~~
# REGISTRATION
# ~~~~~~~~~~~~~~~~
# Register UI panels and sub-panels.


def register() -> None:
    """Register classes."""
    bpy.utils.register_class(SBT_PT_SidebarPanel)
    bpy.utils.register_class(SBT_PT_ShapeKeyTransfer)
    bpy.utils.register_class(SBT_PT_MergeVertexGroups)


def unregister() -> None:
    """Unregister classes."""
    bpy.utils.unregister_class(SBT_PT_MergeVertexGroups)
    bpy.utils.unregister_class(SBT_PT_ShapeKeyTransfer)
    bpy.utils.unregister_class(SBT_PT_SidebarPanel)
