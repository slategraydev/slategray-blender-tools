# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Entry point for Slategray Blender Tools."""

import importlib
import sys

from . import ui, utils
from .modules import apply_modifiers, apply_rest_pose, clean_vertex_groups, transfer_shape_keys

# ------------------------------------------------------------------------------
# ADDON METADATA
# ------------------------------------------------------------------------------

bl_info = {
    "name": "Slategray Blender Tools",
    "author": "Randall Rosas (Slategray)",
    "blender": (3, 6, 0),
    "version": (1, 1, 0),
    "location": "3D View > Sidebar > SLATE",
    "description": "A modular tool suite for mesh and rigging workflows.",
    "category": "Object",
}

# ------------------------------------------------------------------------------
# DYNAMIC RELOADING
# ------------------------------------------------------------------------------

MODULE_NAMES = (
    "utils",
    "ui",
    "modules.apply_modifiers",
    "modules.apply_rest_pose",
    "modules.clean_vertex_groups",
    "modules.transfer_shape_keys",
)

if "bpy" in sys.modules:
    for name in MODULE_NAMES:
        full_name = f"{__package__}.{name}" if __package__ else name
        if full_name in sys.modules:
            importlib.reload(sys.modules[full_name])


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------

MODULES = (
    ui,
    apply_modifiers,
    apply_rest_pose,
    clean_vertex_groups,
    transfer_shape_keys,
)


def register() -> None:
    """Register all modular components."""
    utils.register_modules(MODULES)


def unregister() -> None:
    """Unregister all modular components."""
    utils.unregister_modules(MODULES)


if __name__ == "__main__":
    register()
