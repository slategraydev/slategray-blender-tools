# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""High-performance Blender addon to bake modifiers using NumPy vectorization."""

import time

import bpy  # type: ignore
import numpy as np
from bpy.props import (  # type: ignore
    BoolProperty,
    CollectionProperty,
    StringProperty,
)

# --- Addon Definition ---

bl_info = {
    "name": "Apply Modifiers",
    "author": "Randall Rosas (Slategray)",
    "blender": (5, 0, 0),
    "version": "1.0.0",
    "location": "Object > Context Menu",
    "description": "Bakes modifiers while preserving shape keys using NumPy vectorization.",
    "category": "Object",
}

# --- Configuration & Constants ---


class MSK_ModifierItem(bpy.types.PropertyGroup):
    """Storage for individual modifier selection across multiple objects."""

    obj_name: StringProperty()  # type: ignore
    mod_name: StringProperty()  # type: ignore
    is_selected: BoolProperty(name="Apply", default=True)  # type: ignore


SHAPE_ATTRIBUTES = (
    "interpolation",
    "mute",
    "name",
    "slider_max",
    "slider_min",
    "value",
    "vertex_group",
)

# --- Private Utilities: Data Capture ---


def _capture_mesh_metadata(
    mesh_data: bpy.types.Mesh,
) -> tuple[list[dict], list[tuple[float, bool]]]:
    """Record shape key metadata and current state."""
    if not mesh_data.shape_keys:
        return [], []

    key_blocks = mesh_data.shape_keys.key_blocks
    metadata = [
        {
            **{a: getattr(kb, a) for a in SHAPE_ATTRIBUTES},
            "rel": kb.relative_key.name if kb.relative_key else kb.name,
        }
        for kb in key_blocks
    ]
    original_state = [(kb.value, kb.mute) for kb in key_blocks]
    return metadata, original_state


def _capture_modifier_stack(ob: bpy.types.Object) -> list[dict]:
    """Capture a snapshot of the entire modifier stack."""
    snaps = []
    for m in ob.modifiers:
        snap = {"name": m.name, "type": m.type, "show_viewport": m.show_viewport}
        for p in m.bl_rna.properties:
            if not p.is_readonly and p.identifier not in {"name", "type"}:
                snap[p.identifier] = getattr(m, p.identifier)
        snaps.append(snap)
    return snaps


# --- Private Utilities: Extraction ---


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
    coord_buffer = None

    for kb in key_blocks:
        kb.mute, kb.value = True, 0.0

    for i in range(total_shapes):
        kb = key_blocks[i]
        kb.mute, kb.value = False, 1.0

        ob.update_tag()
        depsgraph.update()

        eval_obj = ob.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()

        current_count = len(temp_mesh.vertices)
        if i == 0:
            reference_vert_count = current_count
            coord_buffer = np.empty(reference_vert_count * 3, dtype=np.float32)
        elif current_count != reference_vert_count:
            eval_obj.to_mesh_clear()
            return None, "Topology mismatch detected."

        if coord_buffer is not None:
            temp_mesh.vertices.foreach_get("co", coord_buffer)
            coords_collection.append(coord_buffer.copy())

        eval_obj.to_mesh_clear()
        kb.mute, kb.value = True, 0.0

    return reference_vert_count, coords_collection


def _extract_mesh_data_world(
    ob: bpy.types.Object,
    context: bpy.types.Context,
    target_modifiers: list[str],
) -> tuple[list[dict], list[np.ndarray]] | tuple[None, str]:
    """Capture vertex coordinates in WORLD SPACE to stabilize against transform issues."""
    mesh_data = ob.data
    matrix_world = np.array(ob.matrix_world)
    metadata, original_state = _capture_mesh_metadata(mesh_data)

    # Configure visibility
    orig_vis = {m.name: m.show_viewport for m in ob.modifiers}
    for m in ob.modifiers:
        m.show_viewport = m.name in target_modifiers

    try:
        if not mesh_data.shape_keys:
            deps = context.evaluated_depsgraph_get()
            ob.update_tag()
            deps.update()
            eval_ob = ob.evaluated_get(deps)
            temp = eval_ob.to_mesh()
            buf = np.empty(len(temp.vertices) * 3, dtype=np.float32)
            temp.vertices.foreach_get("co", buf)
            coords_local = [buf]
            eval_ob.to_mesh_clear()
        else:
            res = _isolate_and_extract_mesh_data(ob, context)
            if res[0] is None:
                return None, str(res[1])
            _, coords_local = res

        # World-Space stabilization
        coords_world = []
        for c in coords_local:
            v = np.reshape(c, (-1, 3))
            vh = np.c_[v, np.ones(len(v))]
            coords_world.append((matrix_world @ vh.T).T[:, :3].astype(np.float32))

        return metadata, coords_world

    finally:
        # Restore state
        for m in ob.modifiers:
            if m.name in orig_vis:
                m.show_viewport = orig_vis[m.name]
        if mesh_data.shape_keys:
            for i, (val, mute) in enumerate(original_state):
                (
                    mesh_data.shape_keys.key_blocks[i].value,
                    mesh_data.shape_keys.key_blocks[i].mute,
                ) = (
                    val,
                    mute,
                )
        context.view_layer.update()


# --- Private Utilities: Restoration ---


def _restore_geometry(ob: bpy.types.Object, metadata: list[dict], coords_world: list[np.ndarray]):
    """Update base mesh and rebuild shape keys."""
    inv_mat = np.array(ob.matrix_world.inverted())
    coords_local = []
    for cw in coords_world:
        vh = np.c_[cw, np.ones(len(cw))]
        coords_local.append(((inv_mat @ vh.T).T[:, :3]).flatten().astype(np.float32))

    ob.data.vertices.foreach_set("co", coords_local[0])

    if metadata:
        for i, meta in enumerate(metadata):
            kb = ob.shape_key_add(name=meta["name"], from_mix=False)
            kb.data.foreach_set("co", coords_local[i])
            for attr in SHAPE_ATTRIBUTES:
                if attr != "name":
                    setattr(kb, attr, meta[attr])

        blocks = ob.data.shape_keys.key_blocks
        for i, meta in enumerate(metadata):
            rel = meta["rel"]
            if rel in blocks:
                blocks[i].relative_key = blocks[rel]


def _restore_modifier_stack(
    ob: bpy.types.Object, snaps: list[dict], sel_set: set[str], keep_arms: bool
):
    """Rebuild the modifier stack from snapshots."""
    for snap in snaps:
        is_baked = snap["name"] in sel_set
        is_arm = snap["type"] == "ARMATURE"
        hidden = not snap["show_viewport"]
        if (not is_baked) or hidden or (is_arm and keep_arms):
            new_mod = ob.modifiers.new(name=snap["name"], type=snap["type"])
            for key, val in snap.items():
                if key not in {"name", "type"}:
                    try:
                        setattr(new_mod, key, val)
                    except Exception:
                        pass


def _restore_object_clean(
    ob: bpy.types.Object,
    metadata: list[dict],
    coords_world: list[np.ndarray],
    snaps: list[dict],
    sel_mods: list[str],
    keep_arms: bool,
) -> None:
    """Wipe and reconstruct object against the new world state."""
    if ob.data.shape_keys:
        for kb in reversed(ob.data.shape_keys.key_blocks):
            ob.shape_key_remove(kb)
    ob.modifiers.clear()

    _restore_geometry(ob, metadata, coords_world)
    _restore_modifier_stack(ob, snaps, set(sel_mods), keep_arms)


# --- Private Utilities: Rigging ---


def _force_sync_rig(context: bpy.types.Context, arm: bpy.types.Object) -> None:
    """Forcefully apply rest pose to the armature."""
    if not arm or arm.type != "ARMATURE" or arm.library:
        return

    was_hidden = arm.hide_viewport
    arm.hide_viewport = False
    orig_active = context.view_layer.objects.active
    context.view_layer.objects.active = arm
    orig_mode = arm.mode

    try:
        if arm.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.armature_apply()
    except Exception as e:
        print(f"Apply Modifiers: Rig sync failed for '{arm.name}': {e}")
    finally:
        try:
            if arm.mode != orig_mode:
                bpy.ops.object.mode_set(mode=orig_mode)
        except Exception:
            pass
        context.view_layer.objects.active = orig_active
        arm.hide_viewport = was_hidden


# --- UI: Operators ---


class MSK_OT_ApplyModifiers(bpy.types.Operator):
    """Bake and remove modifiers while preserving shape keys."""

    bl_idname = "object.msk_apply_modifiers"
    bl_label = "Apply Modifiers"
    bl_options = {"REGISTER", "UNDO"}

    modifier_items: CollectionProperty(type=MSK_ModifierItem)  # type: ignore

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Apply selected modifiers across the selection."""
        timer_start = time.time()
        groups: dict[str, list[str]] = {}
        for item in self.modifier_items:
            if item.is_selected:
                groups.setdefault(item.obj_name, []).append(item.mod_name)
        if not groups:
            return {"CANCELLED"}

        orig_active = context.view_layer.objects.active
        orig_selected = list(context.selected_objects)

        for name, mods in groups.items():
            ob = bpy.data.objects.get(name)
            if not ob:
                continue

            snaps = _capture_modifier_stack(ob)
            context.view_layer.objects.active = ob
            res = _extract_mesh_data_world(ob, context, mods)
            if res[0] is not None:
                _restore_object_clean(ob, res[0], res[1], snaps, mods, False)

        context.view_layer.objects.active = orig_active
        for o in orig_selected:
            o.select_set(True)

        print(f"Bake finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        """Initialize selection dialog based on viewport visibility."""
        self.modifier_items.clear()
        found = False
        for ob in context.selected_objects:
            if ob.type == "MESH":
                for m in ob.modifiers:
                    item = self.modifier_items.add()
                    item.obj_name, item.mod_name, item.is_selected = (
                        ob.name,
                        m.name,
                        m.show_viewport,
                    )
                    found = True
        if not found:
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context: bpy.types.Context) -> None:
        """Render dialogue UI grouped by object."""
        last = ""
        for item in self.modifier_items:
            if item.obj_name != last:
                last = item.obj_name
                self.layout.label(text=f"Object: {last}", icon="OBJECT_DATA")
                box = self.layout.box()
            box.prop(item, "is_selected", text=item.mod_name, icon="MODIFIER", toggle=True)


class MSK_OT_ApplyRestPose(bpy.types.Operator):
    """Bake pose, update rest pose, and re-apply modifiers."""

    bl_idname = "object.msk_apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Perform one-click rig sync and mesh restoration."""
        timer_start = time.time()
        obs = [o for o in context.selected_objects if o.type == "MESH"]
        if not obs:
            return {"CANCELLED"}

        orig_active = context.view_layer.objects.active
        orig_selected = list(context.selected_objects)

        data_map = {}
        armatures = set()
        for ob in obs:
            snaps = _capture_modifier_stack(ob)
            mods = [m.name for m in ob.modifiers if m.show_viewport]
            for m in ob.modifiers:
                if m.type == "ARMATURE" and m.object:
                    armatures.add(m.object)

            context.view_layer.objects.active = ob
            res = _extract_mesh_data_world(ob, context, mods)
            if res[0] is not None:
                data_map[ob.name] = (res[0], res[1], snaps, mods)

        for arm in armatures:
            _force_sync_rig(context, arm)
        context.view_layer.update()

        for name, (meta, coords, snaps, mods) in data_map.items():
            ob = bpy.data.objects.get(name)
            if ob:
                _restore_object_clean(ob, meta, coords, snaps, mods, True)

        context.view_layer.objects.active = orig_active
        for o in orig_selected:
            o.select_set(True)

        print(f"Rest pose sync finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}


# --- UI: Panel ---


class MSK_PT_SidebarPanel(bpy.types.Panel):
    """Sidebar Panel for quick access to bake tools."""

    bl_idname = "MSK_PT_SidebarPanel"
    bl_label = "Apply Modifiers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context: bpy.types.Context) -> None:
        """Render main action buttons."""
        self.layout.operator(MSK_OT_ApplyModifiers.bl_idname, icon="RECOVER_LAST")
        self.layout.operator(MSK_OT_ApplyRestPose.bl_idname, icon="ARMATURE_DATA")


# --- Registration ---

CLASSES = (
    MSK_ModifierItem,
    MSK_OT_ApplyModifiers,
    MSK_OT_ApplyRestPose,
    MSK_PT_SidebarPanel,
)


def register() -> None:
    """Register all addon classes."""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    """Unregister all addon classes."""
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
