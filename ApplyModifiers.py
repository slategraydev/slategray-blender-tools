# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""High-performance Blender addon to bake modifiers using NumPy vectorization."""

import time
from typing import Any

import bpy  # type: ignore
import numpy as np
from bpy.props import BoolVectorProperty  # type: ignore

# --- Addon Definition ---

bl_info = {
    "name": "Apply Modifiers",
    "author": "Randall Rosas (Slategray)",
    "blender": (5, 0, 0),
    "version": (1, 0, 0),
    "location": "Object > Context Menu",
    "description": "Bakes modifiers while preserving shape keys using NumPy vectorization.",
    "category": "Object",
}

# --- Configuration & State ---

MAX_MODIFIERS = 32

SHAPE_ATTRIBUTES = (
    "interpolation",
    "mute",
    "name",
    "slider_max",
    "slider_min",
    "value",
    "vertex_group",
)

# --- High-Performance Mesh Processing ---


def _isolate_and_extract_mesh_data(
    ob: bpy.types.Object,
    context: bpy.types.Context,
) -> tuple[int, list[np.ndarray]] | tuple[None, str]:
    """Evaluate and extract vertex coordinates using NumPy buffers."""
    coords_collection: list[np.ndarray] = []
    depsgraph = context.evaluated_depsgraph_get()
    key_blocks = ob.data.shape_keys.key_blocks
    total_shapes = len(key_blocks)

    reference_vert_count = -1
    coord_buffer: np.ndarray | None = None

    for i in range(total_shapes):
        for j, kb in enumerate(key_blocks):
            kb.value = 1.0 if i == j else 0.0
            kb.mute = i != j

        context.view_layer.update()
        eval_obj = ob.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()

        current_count = len(temp_mesh.vertices)
        if i == 0:
            reference_vert_count = current_count
            coord_buffer = np.empty(reference_vert_count * 3, dtype=np.float32)
        elif current_count != reference_vert_count:
            eval_obj.to_mesh_clear()
            return None, "Topology mismatch detected during bake."

        if coord_buffer is not None:
            temp_mesh.vertices.foreach_get("co", coord_buffer)
            coords_collection.append(coord_buffer.copy())

        eval_obj.to_mesh_clear()

    return reference_vert_count, coords_collection


def _rebuild_geometry_stack(
    ob: bpy.types.Object,
    metadata: list[dict[str, Any]],
    baked_data: list[np.ndarray],
) -> None:
    """Restore shape keys using vectorized NumPy data."""
    for i, meta in enumerate(metadata):
        new_kb = ob.shape_key_add(name=meta["name"], from_mix=False)
        new_kb.data.foreach_set("co", baked_data[i])
        for attr in SHAPE_ATTRIBUTES:
            if attr != "name":
                setattr(new_kb, attr, meta[attr])

    key_blocks = ob.data.shape_keys.key_blocks
    for i, meta in enumerate(metadata):
        rel_target = meta["rel"]
        if rel_target in key_blocks:
            key_blocks[i].relative_key = key_blocks[rel_target]


# --- Logic Coordination ---


def _configure_stack_visibility(
    ob: bpy.types.Object,
    target_modifiers: list[str],
) -> dict[str, bool]:
    """Configure modifier visibility and return original state."""
    original_vis = {m.name: m.show_viewport for m in ob.modifiers}
    for m in ob.modifiers:
        m.show_viewport = m.name in target_modifiers
    return original_vis


def _bake_and_rebuild(
    ob: bpy.types.Object,
    target_modifiers: list[str],
    metadata: list[dict[str, Any]],
    baked_coords: list[np.ndarray],
) -> None:
    """Apply modifiers and rebuild the vectorized shape key stack."""
    bpy.ops.object.shape_key_remove(all=True)
    for mod_name in target_modifiers:
        if mod_name in ob.modifiers:
            bpy.ops.object.modifier_apply(modifier=mod_name)
    _rebuild_geometry_stack(ob, metadata, baked_coords)


def _execute_vectorized_bake(
    context: bpy.types.Context,
    target_modifiers: list[str],
) -> tuple[bool, str | None]:
    """Orchestrates the high-performance bake pipeline."""
    ob = context.object
    if not ob or ob.type != "MESH":
        return False, "Active object must be a mesh."

    timer_start = time.time()
    mesh_data = ob.data

    if not mesh_data.shape_keys:
        for mod_name in target_modifiers:
            if mod_name in ob.modifiers:
                bpy.ops.object.modifier_apply(modifier=mod_name)
        return True, None

    serialized_keys = [
        {**{attr: getattr(kb, attr) for attr in SHAPE_ATTRIBUTES}, "rel": kb.relative_key.name}
        for kb in mesh_data.shape_keys.key_blocks
    ]

    original_vis = _configure_stack_visibility(ob, target_modifiers)
    original_state = [(kb.value, kb.mute) for kb in mesh_data.shape_keys.key_blocks]

    try:
        res = _isolate_and_extract_mesh_data(ob, context)
        if res[0] is None:
            return False, str(res[1])
        _, baked_coords = res
    finally:
        for m in ob.modifiers:
            if m.name in original_vis:
                m.show_viewport = original_vis[m.name]
        for idx, kb in enumerate(mesh_data.shape_keys.key_blocks):
            kb.value, kb.mute = original_state[idx]

    _bake_and_rebuild(ob, target_modifiers, serialized_keys, baked_coords)

    print(f"Vectorized bake finished in {time.time() - timer_start:.4f}s")
    return True, None


# --- UI: Operator ---


class MSK_OT_BakeVectorized(bpy.types.Operator):
    """Bake modifiers with high-performance NumPy vectorization."""

    bl_idname = "object.msk_bake_vectorized"
    bl_label = "Apply Modifiers"
    bl_options = {"REGISTER", "UNDO"}

    selected_modifiers: BoolVectorProperty(  # type: ignore
        name="Selected Modifiers",
        size=MAX_MODIFIERS,
        default=(True,) * MAX_MODIFIERS,
    )

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Run vectorized bake execution."""
        ob = context.object
        if not ob:
            return {"CANCELLED"}

        all_mods = [m.name for m in ob.modifiers]
        selected = [
            name
            for i, name in enumerate(all_mods)
            if i < MAX_MODIFIERS and self.selected_modifiers[i]
        ]

        if not selected:
            self.report({"WARNING"}, "No modifiers selected for bake.")
            return {"CANCELLED"}

        success, error = _execute_vectorized_bake(context, selected)
        if not success:
            self.report({"ERROR"}, error if error else "Bake failed.")
            return {"CANCELLED"}

        return {"FINISHED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Render dialogue and redo panel."""
        ob = context.object
        if not ob:
            return

        layout = self.layout
        layout.label(text="Select modifiers to bake:")

        box = layout.box()
        armature_selected = False

        for i, mod in enumerate(ob.modifiers):
            if i >= MAX_MODIFIERS:
                break

            # Draw as toggle buttons for high-contrast selection
            # Selected = Highlighted/Light Gray, Unselected = Flat/Dark Gray
            box.prop(
                self, "selected_modifiers", index=i, text=mod.name, icon="MODIFIER", toggle=True
            )

            if self.selected_modifiers[i] and mod.type == "ARMATURE":
                armature_selected = True

        if armature_selected:
            col = layout.column(align=True)
            col.alert = True
            col.label(text="Warning: Armature selected.", icon="ERROR")
            col.label(text="This will bake the current pose.")

    def invoke(self, context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        """Initialize selection based on current viewport visibility."""
        ob = context.object
        if not ob:
            return {"CANCELLED"}

        # Initialize the vector based on current visibility
        temp_selection = [False] * MAX_MODIFIERS
        for i, mod in enumerate(ob.modifiers):
            if i < MAX_MODIFIERS:
                temp_selection[i] = mod.show_viewport

        self.selected_modifiers = tuple(temp_selection)

        return context.window_manager.invoke_props_dialog(self)


# --- UI: Panel ---


class MSK_PT_SidebarPanel(bpy.types.Panel):
    """Sidebar Panel."""

    bl_idname = "MSK_PT_SidebarPanel"
    bl_label = "Apply Modifiers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context: bpy.types.Context) -> None:
        """Render UI button."""
        self.layout.operator(MSK_OT_BakeVectorized.bl_idname, icon="RECOVER_LAST")


# --- Registration ---

CLASSES = (
    MSK_OT_BakeVectorized,
    MSK_PT_SidebarPanel,
)


def register() -> None:
    """Register addon."""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    """Unregister addon."""
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
