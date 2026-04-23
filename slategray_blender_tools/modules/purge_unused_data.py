# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray). All rights reserved.
# ------------------------------------------------------------------------------

"""Operator for purging unused data-blocks from the Blender file."""

import time

import bpy  # type: ignore

# ~~~~~~~~~~~~~~~~
# OPERATOR LOGIC
# ~~~~~~~~~~~~~~~~
# Logic for identifying and removing orphan data-blocks.


class SBT_OT_PurgeUnusedData(bpy.types.Operator):
    """Remove all unused data-blocks (textures, materials, meshes, etc.)."""

    bl_idname = "object.sbt_purge_unused_data"
    bl_label = "Purge Unused Data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Purge orphan data-blocks recursively."""
        timer_start = time.time()

        # Initial counts
        before_counts = self._get_data_counts()

        # Recursively purge until no more orphans are found
        # (Deleting a material might make a texture an orphan, etc.)
        # bpy.data.orphans_purge(do_recursive=True) is available in newer Blender versions.
        # We will use the operator to ensure it works across different versions if possible,
        # but the data method is cleaner.

        try:
            bpy.data.orphans_purge(do_recursive=True)
        except Exception:
            # Fallback for older API if recursive isn't supported as a kwarg
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        after_counts = self._get_data_counts()

        purged_report = []
        for key in before_counts:
            diff = before_counts[key] - after_counts.get(key, 0)
            if diff > 0:
                purged_report.append(f"{key}: {diff}")

        if not purged_report:
            self.report({"INFO"}, "No unused data found.")
        else:
            report_str = ", ".join(purged_report)
            self.report({"INFO"}, f"Purged: {report_str}")

        print(f"Purge Unused Data: Finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}

    def _get_data_counts(self) -> dict[str, int]:
        """Get counts of major data-block types."""
        return {
            "Meshes": len(bpy.data.meshes),
            "Materials": len(bpy.data.materials),
            "Textures": len(bpy.data.textures),
            "Images": len(bpy.data.images),
            "Actions": len(bpy.data.actions),
            "Node Groups": len(bpy.data.node_groups),
        }


# ~~~~~~~~~~~~~~~~
# REGISTRATION
# ~~~~~~~~~~~~~~~~
# Standard Blender registration for the purge operator.


def register() -> None:
    """Register class."""
    bpy.utils.register_class(SBT_OT_PurgeUnusedData)


def unregister() -> None:
    """Unregister class."""
    bpy.utils.unregister_class(SBT_OT_PurgeUnusedData)
