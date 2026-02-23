# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Addon lifecycle and registration helpers."""

# ------------------------------------------------------------------------------
# ADDON LIFECYCLE HELPERS
# ------------------------------------------------------------------------------


def register_modules(modules: tuple) -> None:
    """Register all modular components."""
    for mod in modules:
        if hasattr(mod, "register"):
            mod.register()


def unregister_modules(modules: tuple) -> None:
    """Unregister all modular components."""
    for mod in reversed(modules):
        if hasattr(mod, "unregister"):
            mod.unregister()
