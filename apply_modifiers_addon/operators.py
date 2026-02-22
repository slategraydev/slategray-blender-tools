# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Main operators for the Apply Modifiers addon."""

import time

import bpy  # type: ignore
import numpy as np
from bpy.props import (  # type: ignore
    BoolProperty,
    CollectionProperty,
    StringProperty,
)

from .utils import (
    SHAPE_ATTRIBUTES,
    apply_armature_rest_pose,
    extract_mesh_data,
    get_modifier_snapshot,
    restore_object,
)


class MSK_ModifierItem(bpy.types.PropertyGroup):
    """Storage for individual modifier selection."""

    obj_name: StringProperty()  # type: ignore
    mod_name: StringProperty()  # type: ignore
    is_selected: BoolProperty(name="Apply", default=True)  # type: ignore


class MSK_OT_ApplyModifiers(bpy.types.Operator):
    """Bake and remove modifiers while preserving shape keys."""

    bl_idname = "object.msk_apply_modifiers"
    bl_label = "Apply Modifiers"
    bl_options = {"REGISTER", "UNDO"}

    modifier_items: CollectionProperty(type=MSK_ModifierItem)  # type: ignore

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Apply selected modifiers to the selection."""
        timer_start = time.time()
        groups: dict[str, list[str]] = {}
        for item in self.modifier_items:
            if item.is_selected:
                groups.setdefault(item.obj_name, []).append(item.mod_name)

        if not groups:
            self.report({"WARNING"}, "No modifiers selected.")
            return {"CANCELLED"}

        orig_active = context.view_layer.objects.active
        orig_selected = list(context.selected_objects)

        for obj_name, sel_mods in groups.items():
            ob = bpy.data.objects.get(obj_name)
            if not ob:
                continue

            # 1. Snapshot Stack
            snaps = [get_modifier_snapshot(m) for m in ob.modifiers]

            # 2. Extract Data
            context.view_layer.objects.active = ob
            if ob.data.shape_keys:
                meta = [
                    {
                        **{a: getattr(kb, a) for a in SHAPE_ATTRIBUTES},
                        "rel": kb.relative_key.name if kb.relative_key else kb.name,
                    }
                    for kb in ob.data.shape_keys.key_blocks
                ]
                res = extract_mesh_data(ob, context)
                if res[0] is None:
                    continue
                _, coords = res
            else:
                meta = []
                deps = context.evaluated_depsgraph_get()
                ob.update_tag()
                deps.update()
                eval_ob = ob.evaluated_get(deps)
                temp = eval_ob.to_mesh()
                buf = np.empty(len(temp.vertices) * 3, dtype=np.float32)
                temp.vertices.foreach_get("co", buf)
                coords = [buf]
                eval_ob.to_mesh_clear()

            # 3. Restore
            restore_object(ob, meta, coords, snaps, sel_mods, False)

        context.view_layer.objects.active = orig_active
        for o in orig_selected:
            o.select_set(True)

        print(f"Apply Modifiers: Bake finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        """Show selection dialogue."""
        self.modifier_items.clear()
        found = False
        for ob in context.selected_objects:
            if ob.type == "MESH":
                    item.obj_name, item.mod_name, item.is_selected = (
                        ob.name,
                        m.name,
                        m.show_viewport,
                    )
                    item = self.modifier_items.add()
                    item.obj_name, item.mod_name, item.is_selected = ob.name, m.name, m.show_viewport
                    found = True
        if not found:
            self.report({"WARNING"}, "No modifiers found on selected meshes.")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context: bpy.types.Context) -> None:
        """Render dialogue UI."""
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
        """Perform one-click rig and mesh sync."""
        timer_start = time.time()
        obs = [o for o in context.selected_objects if o.type == "MESH"]
        if not obs:
            self.report({"WARNING"}, "No mesh objects selected.")
            return {"CANCELLED"}

        orig_active = context.view_layer.objects.active
        orig_selected = list(context.selected_objects)

        # 1. Capture Everything
        data_map = {}
        armatures = set()
        for ob in obs:
            snaps = [get_modifier_snapshot(m) for m in ob.modifiers]
            sel_mods = [m.name for m in ob.modifiers if m.show_viewport]
            for m in ob.modifiers:
                if m.type == "ARMATURE" and m.object:
                    armatures.add(m.object)

            context.view_layer.objects.active = ob
            if ob.data.shape_keys:
                meta = [
                    {
                        **{a: getattr(kb, a) for a in SHAPE_ATTRIBUTES},
                        "rel": kb.relative_key.name if kb.relative_key else kb.name,
                    }
                    for kb in ob.data.shape_keys.key_blocks
                ]
                res = extract_mesh_data(ob, context)
                if res[0] is None:
                    continue
                _, coords = res
            else:
                meta = []
                deps = context.evaluated_depsgraph_get()
                ob.update_tag()
                deps.update()
                eval_ob = ob.evaluated_get(deps)
                temp = eval_ob.to_mesh()
                buf = np.empty(len(temp.vertices) * 3, dtype=np.float32)
                temp.vertices.foreach_get("co", buf)
                coords = [buf]
                eval_ob.to_mesh_clear()

            data_map[ob.name] = (meta, coords, snaps, sel_mods)

        # 2. Sync Rigs
        for arm in armatures:
            apply_armature_rest_pose(context, arm)
        context.view_layer.update()

        # 3. Restore Meshes against the new rigs
        for name, (meta, coords, snaps, sel_mods) in data_map.items():
            ob = bpy.data.objects.get(name)
            if ob:
                restore_object(ob, meta, coords, snaps, sel_mods, True)

        context.view_layer.objects.active = orig_active
        for o in orig_selected:
            o.select_set(True)

        print(f"Apply Rest Pose: Sync finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}
