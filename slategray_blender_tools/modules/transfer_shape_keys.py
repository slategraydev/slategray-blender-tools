# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Simplified high-performance shape key transfer with automated surface anchoring."""

import time

import bpy  # type: ignore
import numpy as np
from bpy.props import IntProperty, StringProperty  # type: ignore
from mathutils import kdtree  # type: ignore

# Constants
EPSILON = 1e-6
MIN_MESH_COUNT = 2

# ------------------------------------------------------------------------------
# NUMPY UTILITIES
# ------------------------------------------------------------------------------


def apply_matrix_numpy(coords, matrix):
    """Apply a 4x4 matrix to coordinates. Supports (N, 3) or (K, N, 3)."""
    mat_np = np.array(matrix, dtype=np.float32).reshape(4, 4)
    mat_3x3 = mat_np[:3, :3]
    translation = mat_np[:3, 3]

    # Vectorized (SIMD) transformation without homogenous coordinate expansion
    # This avoids doubling memory and allows direct register utilization.
    return (coords @ mat_3x3.T) + translation


def apply_matrix_to_normals(normals, matrix):
    """Apply rotation/scale to normals and re-normalize."""
    mat_3x3 = np.array(matrix).reshape(4, 4)[:3, :3]
    new_normals = normals @ mat_3x3.T
    norms = np.linalg.norm(new_normals, axis=1, keepdims=True)
    return new_normals / np.where(norms > EPSILON, norms, 1.0)


def get_adjacency(mesh):
    """Generate dense adjacency map for 4D tensor smoothing."""
    # Build list of neighbor sets
    adj = [set() for _ in range(len(mesh.vertices))]
    for edge in mesh.edges:
        u, v = edge.vertices
        adj[u].add(v)
        adj[v].add(u)

    # Convert to dense map with padding
    counts = np.array([len(neighbors) for neighbors in adj], dtype=np.float32).reshape(-1, 1)
    max_valence = int(np.max(counts))

    # Pad with 0, but counts will handle the math
    adj_map = np.zeros((len(mesh.vertices), max_valence), dtype=np.int32)
    for i, neighbors in enumerate(adj):
        if neighbors:
            adj_map[i, : len(neighbors)] = list(neighbors)

    return adj_map, counts


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

        # 1. Prepare Data
        prep_data = self._prepare_data(source_obj, target_obj)

        # 2. Process Shape Keys
        total_transferred = self._process_shape_keys(source_obj, target_obj, prep_data)

        # Reset both objects to Basis shape key (index 0)
        source_obj.active_shape_key_index = 0
        target_obj.active_shape_key_index = 0

        self.report({"INFO"}, f"Transferred {total_transferred} keys with Surface Anchoring.")
        print(f"Transfer Shape Keys: Finished in {time.time() - timer_start:.4f}s")
        return {"FINISHED"}

    def _prepare_data(self, source_obj: bpy.types.Object, target_obj: bpy.types.Object) -> dict:
        """Capture and map data between meshes."""
        # Source (Body) Data
        source_mesh = source_obj.data
        source_keys = source_mesh.shape_keys.key_blocks
        source_vert_count = len(source_mesh.vertices)
        source_matrix = source_obj.matrix_world

        source_ref_key = source_mesh.shape_keys.reference_key
        source_local_basis = np.empty(source_vert_count * 3, dtype=np.float32)
        source_ref_key.data.foreach_get("co", source_local_basis)
        source_local_basis.shape = (source_vert_count, 3)
        source_world_basis = apply_matrix_numpy(source_local_basis, source_matrix)

        # Get Source Normals
        source_local_normals = np.empty(source_vert_count * 3, dtype=np.float32)
        source_mesh.vertices.foreach_get("normal", source_local_normals)
        source_local_normals.shape = (source_vert_count, 3)
        source_world_normals = apply_matrix_to_normals(source_local_normals, source_matrix)

        # Build KDTree
        kd = kdtree.KDTree(source_vert_count)
        for i, co in enumerate(source_world_basis):
            kd.insert(co, i)
        kd.balance()

        # Target (Clothing) Data
        target_mesh = target_obj.data
        target_vert_count = len(target_mesh.vertices)
        target_matrix = target_obj.matrix_world

        if not target_mesh.shape_keys:
            target_obj.shape_key_add(name="Basis")

        target_local_basis = np.empty(target_vert_count * 3, dtype=np.float32)
        target_mesh.shape_keys.key_blocks[0].data.foreach_get("co", target_local_basis)
        target_local_basis.shape = (target_vert_count, 3)
        target_world_basis = apply_matrix_numpy(target_local_basis, target_matrix)

        # Surface Mapping
        mapping = np.array([kd.find(co)[1] for co in target_world_basis], dtype=np.int32)

        # Calculate Basis Clearance
        mapped_basis_points = source_world_basis[mapping]
        mapped_basis_normals = source_world_normals[mapping]

        basis_offset = target_world_basis - mapped_basis_points
        basis_clearance = np.sum(basis_offset * mapped_basis_normals, axis=1, keepdims=True)

        # Adjacency for Smoothing
        adj_map, counts = get_adjacency(target_mesh) if self.smooth_iterations > 0 else (None, None)

        return {
            "source_keys": source_keys,
            "source_vert_count": source_vert_count,
            "source_matrix": source_matrix,
            "source_ref_key": source_ref_key,
            "source_world_basis": source_world_basis,
            "target_mesh": target_mesh,
            "target_matrix": target_matrix,
            "target_world_basis": target_world_basis,
            "mapping": mapping,
            "mapped_basis_normals": mapped_basis_normals,
            "basis_clearance": basis_clearance,
            "adj_map": adj_map,
            "neighbor_counts": counts,
        }

    def _process_shape_keys(
        self, source_obj: bpy.types.Object, target_obj: bpy.types.Object, prep: dict
    ) -> int:
        """Iterate and transfer all shape keys using batch 3D/4D tensor logic."""
        source_vert_count = prep["source_vert_count"]
        source_matrix = prep["source_matrix"]
        source_ref_key = prep["source_ref_key"]

        # Collect all source keys into a 3D Tensor (K, V, 3)
        valid_keys = [kb for kb in prep["source_keys"] if kb != source_ref_key]
        if not valid_keys:
            return 0

        key_count = len(valid_keys)
        # All data must be C-Contiguous float32 for maximum L1 Cache hits
        all_source_shapes = np.empty((key_count, source_vert_count, 3), dtype=np.float32, order="C")

        for i, kb in enumerate(valid_keys):
            kb.data.foreach_get("co", all_source_shapes[i].ravel())

        # Fully Vectorized Matrix Application (No loops)
        # This triggers NumPy's internal multi-threaded BLAS/MKL and SIMD extensions
        all_world_shapes = apply_matrix_numpy(all_source_shapes, source_matrix)

        # Vectorized Interpolation (K, V, 3)
        # World Delta = Body[New] - Body[Basis]
        world_deltas_full = all_world_shapes - prep["source_world_basis"]
        # Map body vertex deltas to clothing vertices
        interpolated_deltas = world_deltas_full[:, prep["mapping"]]

        # --- TENSORIZED SMOOTHING (4D GATHER) ---
        if self.smooth_iterations > 0:
            # Contiguous Index Set for TLB hit maximization
            adj_map = np.ascontiguousarray(prep["adj_map"])
            counts = prep["neighbor_counts"]

            for _ in range(self.smooth_iterations):
                # 4D Tensor Gather (K, V, MAX_VALENCE, 3)
                neighbor_deltas = interpolated_deltas[:, adj_map]

                # SIMD: Masked Sum without branching
                mask = np.arange(adj_map.shape[1]) < counts
                mask = mask.astype(np.float32).reshape(1, -1, adj_map.shape[1], 1)

                sum_neighbor_deltas = np.sum(neighbor_deltas * mask, axis=2)
                mean_neighbor_deltas = sum_neighbor_deltas / counts
                interpolated_deltas = (interpolated_deltas + mean_neighbor_deltas) / 2.0

        # --- TENSORIZED SURFACE ANCHORING (3D BROADCAST) ---
        target_world_new_raw = prep["target_world_basis"] + interpolated_deltas
        # mapped_new_points = source_world_shape[mapping] -> (K, TV, 3)
        mapped_new_points = all_world_shapes[:, prep["mapping"]]

        new_offset = target_world_new_raw - mapped_new_points
        # clearance = sum(offset * normals) -> (K, TV, 1)
        new_clearance = np.sum(new_offset * prep["mapped_basis_normals"], axis=2, keepdims=True)

        # Branchless Masked Correction (SIMD-Friendly)
        # If it dipped below the original clearance, push it back.
        correction_mask = (new_clearance < prep["basis_clearance"]).astype(np.float32)
        diff = prep["basis_clearance"] - new_clearance + 0.0001
        interpolated_deltas += correction_mask * diff * prep["mapped_basis_normals"]

        # Fully Vectorized Inverse Transformation
        target_matrix_inv = prep["target_matrix"].inverted()
        target_world_final = prep["target_world_basis"] + interpolated_deltas
        target_local_final = apply_matrix_numpy(target_world_final, target_matrix_inv)

        # Inject back (Loop only for Blender API)
        target_mesh = prep["target_mesh"]
        for i, kb in enumerate(valid_keys):
            target_kb = target_mesh.shape_keys.key_blocks.get(kb.name)
            if not target_kb:
                target_kb = target_obj.shape_key_add(name=kb.name)

            target_kb.value = 0.0
            target_kb.data.foreach_set("co", target_local_final[i].ravel())

        return key_count

    def invoke(self, context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        """Auto-detect selection."""
        meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if len(meshes) < MIN_MESH_COUNT:
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
