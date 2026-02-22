# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Entry point for the Apply Modifiers Blender Addon."""

import bpy  # type: ignore

from .operators import MSK_ModifierItem, MSK_OT_ApplyModifiers, MSK_OT_ApplyRestPose
from .ui import MSK_PT_SidebarPanel

bl_info = {
    "name": "Apply Modifiers",
    "author": "Randall Rosas (Slategray)",
    "blender": (5, 0, 0),
    "version": (1, 0, 0),
    "location": "Object > Context Menu",
    "description": "Bakes modifiers while preserving shape keys using NumPy vectorization.",
    "category": "Object",
}

CLASSES = (
    MSK_ModifierItem,
    MSK_OT_ApplyModifiers,
    MSK_OT_ApplyRestPose,
    MSK_PT_SidebarPanel,
)


def register() -> None:
    """Register all classes with Blender."""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    """Unregister all classes from Blender."""
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
