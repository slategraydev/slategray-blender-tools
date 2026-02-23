# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Simplified high-performance shape key transfer with automated surface anchoring."""

import time

import bpy  # type: ignore
import numpy as np
from bpy.props import IntProperty, StringProperty  # type: ignore
from mathutils import kdtree  # type: ignore

# ------------------------------------------------------------------------------
# NUMPY UTILITIES
# ------------------------------------------------------------------------------


def apply_matrix_numpy(coords, matrix):
    """Apply a 4x4 matrix to (N, 3) coordinates."""
    mat_np = np.array(matrix).reshape(4, 4)
    homog = np.c_[coords, np.ones(coords.shape[0])]
    return (homog @ mat_np.T)[:, :3]


def apply_matrix_to_normals(normals, matrix):
    """Apply rotation/scale to normals and re-normalize."""
    mat_3x3 = np.array(matrix).reshape(4, 4)[:3, :3]
    new_normals = normals @ mat_3x3.T
    norms = np.linalg.norm(new_normals, axis=1, keepdims=True)
    return new_normals / np.where(norms > 1e-6, norms, 1.0)


def get_adjacency(mesh):
    """Generate adjacency list for Laplacian smoothing."""
    adj = [set() for _ in range(len(mesh.vertices))]
    for edge in mesh.edges:
        u, v = edge.vertices
        adj[u].add(v)
        adj[v].add(u)
    return [list(neighbors) for neighbors in adj]


# ------------------------------------------------------------------------------
# OPERATOR LOGIC
# ------------------------------------------------------------------------------


class SBT_OT_TransferShapeKeys(bpy.types.Operator):
    """Transfer ALL shape keys with automated surface anchoring and anti-clipping."""

    bl_idname = "object.sbt_transfer_shape_keys"
    bl_label = "Transfer Shape Keys"
    bl_options = {"REGISTER", "UNDO"}

    source_name: StringProperty(name="Source (Body)")  # type: ignore
    target_name: StringProperty(name="Target (Clothing)")  # type: ignore

    smooth_iterations: IntProperty(
        name="Smoothing Passes",
        default=5,
        min=0,
        max=50,
        description="Number of smoothing iterations. Anti-clipping is handled automatically",
    )  # type: ignore

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Perform surface-anchored delta mapping."""
        timer_start = time.time()

        source_obj = bpy.data.objects.get(self.source_name)
        target_obj = bpy.data.objects.get(self.target_name)

        if not source_obj or not target_obj:
            self.report({"WARNING"}, "Objects not found.")
            return {"CANCELLED"}

        # 1. Capture Source (Body) Data
        source_mesh = source_obj.data
        source_keys = source_mesh.shape_keys.key_blocks
        source_vert_count = len(source_mesh.vertices)
        source_matrix = source_obj.matrix_world

        source_ref_key = source_mesh.shape_keys.reference_key
        source_local_basis = np.empty(source_vert_count * 3, dtype=np.float32)
        source_ref_key.data.foreach_get("co", source_local_basis)
        source_local_basis.shape = (source_vert_count, 3)
        source_world_basis = apply_matrix_numpy(source_local_basis, source_matrix)

        # Get Source Normals for World Space projection
        source_local_normals = np.empty(source_vert_count * 3, dtype=np.float32)
        source_mesh.vertices.foreach_get("normal", source_local_normals)
        source_local_normals.shape = (source_vert_count, 3)
        source_world_normals = apply_matrix_to_normals(source_local_normals, source_matrix)

        # 2. Build KDTree (World Space)
        kd = kdtree.KDTree(source_vert_count)
        for i, co in enumerate(source_world_basis):
            kd.insert(co, i)
        kd.balance()

        # 3. Capture Target (Clothing) Data
        target_mesh = target_obj.data
        target_vert_count = len(target_mesh.vertices)
        target_matrix = target_obj.matrix_world
        target_matrix_inv = target_matrix.inverted()

        if not target_mesh.shape_keys:
            target_obj.shape_key_add(name="Basis")

        target_local_basis = np.empty(target_vert_count * 3, dtype=np.float32)
        target_mesh.shape_keys.key_blocks[0].data.foreach_get("co", target_local_basis)
        target_local_basis.shape = (target_vert_count, 3)
        target_world_basis = apply_matrix_numpy(target_local_basis, target_matrix)

        # 4. Surface Mapping (1-Nearest Neighbor for 1:1 Magnitude)
        mapping = np.array([kd.find(co)[1] for co in target_world_basis], dtype=np.int32)

        # 5. Profiling: Calculate Basis Clearance
        mapped_basis_points = source_world_basis[mapping]
        mapped_basis_normals = source_world_normals[mapping]

        basis_offset = target_world_basis - mapped_basis_points
        # The exact distance from the skin along the skin's normal
        basis_clearance = np.sum(basis_offset * mapped_basis_normals, axis=1, keepdims=True)

        # 6. Adjacency for Smoothing
        adjacency = get_adjacency(target_mesh) if self.smooth_iterations > 0 else []

        # 7. Process Shape Keys
        total_transferred = 0
        source_local_shape = np.empty(source_vert_count * 3, dtype=np.float32)

        for kb in source_keys:
            if kb == source_ref_key:
                continue

            # Extract body shape
            kb.data.foreach_get("co", source_local_shape)
            source_local_shape.shape = (source_vert_count, 3)
            source_world_shape = apply_matrix_numpy(source_local_shape, source_matrix)

            # World Delta (1:1 Movement)
            world_deltas_full = source_world_shape - source_world_basis
            interpolated_deltas = world_deltas_full[mapping]

            # --- SMOOTHING PASS ---
            if self.smooth_iterations > 0:
                for _ in range(self.smooth_iterations):
                    smooth_deltas = np.copy(interpolated_deltas)
                    for i, neighbors in enumerate(adjacency):
                        if neighbors:
                            avg_neighbor_delta = np.mean(interpolated_deltas[neighbors], axis=0)
                            smooth_deltas[i] = (interpolated_deltas[i] + avg_neighbor_delta) / 2.0
                    interpolated_deltas = smooth_deltas

            # --- AUTOMATED SURFACE ANCHORING ---
            # Enforce that the clothing stays at its original 'hover' height relative to the skin.
            target_world_new_raw = target_world_basis + interpolated_deltas
            mapped_new_points = source_world_shape[mapping]

            # Current distance to the deformed skin
            new_offset = target_world_new_raw - mapped_new_points
            new_clearance = np.sum(new_offset * mapped_basis_normals, axis=1, keepdims=True)

            # Anti-Clipping: If it dipped below the original clearance, push it back.
            # We add a tiny 0.1mm epsilon to guarantee coverage.
            clipping_mask = (new_clearance < basis_clearance).flatten()
            if np.any(clipping_mask):
                correction = (
                    basis_clearance[clipping_mask] - new_clearance[clipping_mask]
                ) + 0.0001
                interpolated_deltas[clipping_mask] += (
                    mapped_basis_normals[clipping_mask] * correction
                )

            # Finalize positions
            target_world_final = target_world_basis + interpolated_deltas
            target_local_final = apply_matrix_numpy(target_world_final, target_matrix_inv)

            # Inject Shape Key
            target_kb = target_mesh.shape_keys.key_blocks.get(kb.name)
            if not target_kb:
                target_kb = target_obj.shape_key_add(name=kb.name)

            target_kb.value = 0.0
            target_kb.data.foreach_set("co", target_local_final.ravel())

            source_local_shape.shape = (source_vert_count * 3,)
            total_transferred += 1

        self.report({"INFO"}, f"Transferred {total_transferred} keys with Surface Anchoring.")
        print(f"Transfer Shape Keys: Finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        """Auto-detect selection."""
        meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if len(meshes) < 2:
            self.report({"WARNING"}, "Select Body then Clothing.")
            return {"CANCELLED"}

        active = context.view_layer.objects.active
        if active and active.type == "MESH":
            self.target_name = active.name
            for m in meshes:
                if m.name != self.target_name:
                    self.source_name = m.name
                    break
        else:
            self.source_name = meshes[0].name
            self.target_name = meshes[1].name

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        """Render UI."""
        layout = self.layout
        layout.prop_search(self, "source_name", bpy.data, "objects", text="Source (Body)")
        layout.prop_search(self, "target_name", bpy.data, "objects", text="Target (Clothing)")

        box = layout.box()
        box.label(text="Options", icon="MOD_SHRINKWRAP")
        box.prop(self, "smooth_iterations", text="Smoothing Passes")

        layout.label(text="Surface Anchoring (1:1 Magnitude & Anti-Clipping).", icon="INFO")


# ------------------------------------------------------------------------------
# REGISTRATION
# ------------------------------------------------------------------------------


def register() -> None:
    """Register class."""
    bpy.utils.register_class(SBT_OT_TransferShapeKeys)


def unregister() -> None:
    """Unregister class."""
    bpy.utils.unregister_class(SBT_OT_TransferShapeKeys)
