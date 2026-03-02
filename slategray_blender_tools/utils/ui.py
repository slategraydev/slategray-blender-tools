# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Shared UI components and registration-heavy utilities."""

import bpy  # type: ignore
from bpy.props import IntProperty, StringProperty  # type: ignore

# ------------------------------------------------------------------------------
# SHARED DATA TYPES
# ------------------------------------------------------------------------------


class SBT_GroupItem(bpy.types.PropertyGroup):
    """Storage for vertex group names in growing lists."""

    name: StringProperty()  # type: ignore


# ------------------------------------------------------------------------------
# SHARED UI OPERATORS
# ------------------------------------------------------------------------------


class SBT_OT_UITrigger(bpy.types.Operator):
    """Generic operator to trigger a property update on another operator."""

    bl_idname = "object.sbt_ui_trigger"
    bl_label = "Trigger"
    bl_options = {"INTERNAL"}

    op_idname: StringProperty()  # type: ignore
    prop_name: StringProperty()  # type: ignore

    # Optional extra data (e.g. for index removal)
    extra_prop: StringProperty()  # type: ignore
    extra_val: IntProperty(default=-1)  # type: ignore

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Trigger the property on the active operator."""
        # This only works if we are in a dialogue and the operator is the active one.
        # In Blender 3.6+ dialogues, props are usually on context.active_operator.
        op = getattr(context, "active_operator", None)
        if not op:
            return {"CANCELLED"}

        # Set extra value if needed (e.g. remove index)
        if self.extra_prop:
            setattr(op, self.extra_prop, self.extra_val)

        # Trigger the main boolean/property
        setattr(op, self.prop_name, not getattr(op, self.prop_name))

        return {"FINISHED"}


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register shared UI components."""
    bpy.utils.register_class(SBT_GroupItem)
    bpy.utils.register_class(SBT_OT_UITrigger)


def unregister() -> None:
    """Unregister shared UI components."""
    bpy.utils.unregister_class(SBT_OT_UITrigger)
    bpy.utils.unregister_class(SBT_GroupItem)
