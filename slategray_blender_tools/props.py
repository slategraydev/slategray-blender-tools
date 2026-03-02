# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Persistent scene-level tool properties for Slategray Blender Tools."""

import bpy  # type: ignore
from bpy.props import (  # type: ignore
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from .utils.ui import SBT_GroupItem

# ------------------------------------------------------------------------------
# SHARED HELPERS
# ------------------------------------------------------------------------------


def update_selection(settings: bpy.types.PropertyGroup) -> None:
    """Auto-detect selection and populate tool properties."""
    meshes = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not meshes:
        return

    active = bpy.context.view_layer.objects.active
    if active and active.type == "MESH":
        settings.target_obj = active
        others = [m for m in meshes if m != active]
        if others:
            settings.source_obj = others[0]
    else:
        settings.target_obj = meshes[0]
        if len(meshes) > 1:
            settings.source_obj = meshes[1]


# ------------------------------------------------------------------------------
# MERGE VERTEX GROUPS SETTINGS
# ------------------------------------------------------------------------------


class SBT_MergeVertexGroupsSettings(bpy.types.PropertyGroup):
    """Scene settings for Merging Vertex Groups."""

    target_group: StringProperty(name="Target Group")  # type: ignore
    delete_sources: BoolProperty(
        name="Delete Sources", default=True, description="Remove source vertex groups after merging"
    )  # type: ignore

    # Collection of source groups to merge into target

    sources: CollectionProperty(type=SBT_GroupItem)  # type: ignore

    mix_mode: EnumProperty(
        name="Mix Mode",
        items=[
            ("ADD", "Add", "Add B's weights to A's weights"),
            ("SUB", "Subtract", "Subtract B's weights from A's weights"),
            ("MUL", "Multiply", "Multiply A's weights by B's weights"),
            ("DIV", "Divide", "Divide A's weights by B's weights"),
            ("DIF", "Difference", "Absolute difference between weights"),
            ("AVG", "Average", "Average of both weights"),
            ("MIN", "Minimum", "Use the smaller weight"),
            ("MAX", "Maximum", "Use the larger weight"),
            ("SET", "Replace", "Replace A's weights with B's weights"),
        ],
        default="ADD",
    )  # type: ignore

    mix_set: EnumProperty(
        name="Vertex Set",
        items=[
            ("ALL", "All", "Affect all vertices"),
            ("A", "Vertex Group A", "Affect only vertices in Group A"),
            ("B", "Vertex Group B", "Affect only vertices in Group B"),
            ("OR", "VGroup A or B", "Affect vertices in either group"),
            ("AND", "VGroup A and B", "Affect only vertices in both groups"),
        ],
        default="ALL",
    )  # type: ignore

    # UI Pickers
    def _get_vgs(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            return [("NONE", "No Mesh Selected", "")]
        return [(vg.name, vg.name, "") for vg in obj.vertex_groups]

    def _get_source_vgs(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            return [("NONE", "No Mesh Selected", "")]
        existing = {item.name for item in self.sources}
        items = [("NONE", "Add Source Group...", "")]
        items.extend(
            [(vg.name, vg.name, "") for vg in obj.vertex_groups if vg.name not in existing]
        )
        return items

    def _update_source_picker(self, context):
        if self.source_picker != "NONE":
            self.sources.add().name = self.source_picker
            self.source_picker = "NONE"

    def _update_target_picker(self, context):
        if self.target_picker != "NONE":
            self.target_group = self.target_picker

    target_picker: EnumProperty(items=_get_vgs, name="Target Picker", update=_update_target_picker)  # type: ignore
    source_picker: EnumProperty(items=_get_source_vgs, update=_update_source_picker)  # type: ignore


# ------------------------------------------------------------------------------
# SHAPE KEY TRANSFER SETTINGS
# ------------------------------------------------------------------------------


class SBT_ShapeKeyTransferSettings(bpy.types.PropertyGroup):
    """Scene settings for Shape Key Transfer."""

    source_obj: PointerProperty(type=bpy.types.Object, name="Base Object")  # type: ignore
    target_obj: PointerProperty(type=bpy.types.Object, name="Target Object")  # type: ignore

    smooth_iterations: IntProperty(
        name="Smoothing Passes",
        default=5,
        min=0,
        max=50,
    )  # type: ignore

    target_ignored: CollectionProperty(type=SBT_GroupItem)  # type: ignore

    def _get_target_groups(self, context):
        obj = self.target_obj
        if not obj or obj.type != "MESH":
            return [("NONE", "No Target Object", "")]
        existing = {item.name for item in self.target_ignored}
        items = [("NONE", "Add Mask Group...", "")]
        items.extend(
            [(vg.name, vg.name, "") for vg in obj.vertex_groups if vg.name not in existing]
        )
        return items

    def _update_target_picker(self, context):
        if self.target_picker != "NONE":
            self.target_ignored.add().name = self.target_picker
            self.target_picker = "NONE"

    target_picker: EnumProperty(items=_get_target_groups, update=_update_target_picker)  # type: ignore


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register tool settings."""
    bpy.utils.register_class(SBT_MergeVertexGroupsSettings)
    bpy.utils.register_class(SBT_ShapeKeyTransferSettings)
    bpy.types.Scene.sbt_merge_vgs = PointerProperty(type=SBT_MergeVertexGroupsSettings)
    bpy.types.Scene.sbt_shape_key_transfer = PointerProperty(type=SBT_ShapeKeyTransferSettings)


def unregister() -> None:
    """Unregister tool settings."""
    del bpy.types.Scene.sbt_merge_vgs
    del bpy.types.Scene.sbt_shape_key_transfer
    bpy.utils.unregister_class(SBT_ShapeKeyTransferSettings)
    bpy.utils.unregister_class(SBT_MergeVertexGroupsSettings)
