# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Operator for baking and removing modifiers while preserving shape keys."""

import time

import bpy  # type: ignore
from bpy.props import BoolProperty, CollectionProperty, StringProperty  # type: ignore

from ..utils import capture_mesh_snapshot, get_modifier_snapshot, restore_object

# ------------------------------------------------------------------------------
# DATA TYPES
# ------------------------------------------------------------------------------


class SBT_ModifierItem(bpy.types.PropertyGroup):
    """Storage for individual modifier selection."""

    obj_name: StringProperty()  # type: ignore
    mod_name: StringProperty()  # type: ignore
    is_selected: BoolProperty(name="Apply", default=True)  # type: ignore


# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


class SBT_OT_ApplyModifiers(bpy.types.Operator):
    """Bake and remove modifiers while preserving shape keys."""

    bl_idname = "object.sbt_apply_modifiers"
    bl_label = "Apply Modifiers"
    bl_options = {"REGISTER", "UNDO"}

    modifier_items: CollectionProperty(type=SBT_ModifierItem)  # type: ignore

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

            snaps = [get_modifier_snapshot(m) for m in ob.modifiers]
            context.view_layer.objects.active = ob
            meta, coords = capture_mesh_snapshot(ob, context)
            if meta is None or coords is None:
                continue

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
                for m in ob.modifiers:
                    item = self.modifier_items.add()
                    item.obj_name = ob.name
                    item.mod_name = m.name
                    item.is_selected = m.show_viewport
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


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register classes."""
    bpy.utils.register_class(SBT_ModifierItem)
    bpy.utils.register_class(SBT_OT_ApplyModifiers)


def unregister() -> None:
    """Unregister classes."""
    bpy.utils.unregister_class(SBT_OT_ApplyModifiers)
    bpy.utils.unregister_class(SBT_ModifierItem)
