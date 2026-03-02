# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Entry point for Slategray Blender Tools."""

import importlib
import sys

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
    "utils.lifecycle",
    "utils.performance",
    "utils.mesh",
    "utils.rigging",
    "utils.ui",
    "utils",
    "props",
    "ui",
    "modules.apply_modifiers",
    "modules.apply_rest_pose",
    "modules.clean_vertex_groups",
    "modules.transfer_shape_keys",
    "modules.merge_vertex_groups",
)

if "bpy" in sys.modules:
    for name in MODULE_NAMES:
        full_name = f"{__package__}.{name}" if __package__ else name
        if full_name in sys.modules:
            importlib.reload(sys.modules[full_name])

# ------------------------------------------------------------------------------
# CORE IMPORTS (AFTER RELOAD)
# ------------------------------------------------------------------------------

from . import props, ui, utils  # noqa: E402
from .modules import (  # noqa: E402
    apply_modifiers,
    apply_rest_pose,
    clean_vertex_groups,
    merge_vertex_groups,
    transfer_shape_keys,
)

# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------

MODULES = (
    utils.ui,
    props,
    ui,
    apply_modifiers,
    apply_rest_pose,
    clean_vertex_groups,
    transfer_shape_keys,
    merge_vertex_groups,
)


def register() -> None:
    """Register all modular components."""
    utils.register_modules(MODULES)


def unregister() -> None:
    """Unregister all modular components."""
    utils.unregister_modules(MODULES)


if __name__ == "__main__":
    register()
