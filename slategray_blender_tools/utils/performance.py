# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""High-performance vectorized NumPy utilities for 3D operations."""

from typing import Any

import bpy  # type: ignore
import numpy as np

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------------------

EPSILON = 1e-6

# ------------------------------------------------------------------------------
# VECTORIZED NUMPY UTILITIES
# ------------------------------------------------------------------------------


def apply_matrix_numpy(coords: np.ndarray, matrix: Any) -> np.ndarray:
    """Apply a 4x4 matrix to coordinates with SIMD-friendly vectorization."""
    mat_np = np.array(matrix, dtype=np.float32).reshape(4, 4)
    mat_3x3 = mat_np[:3, :3]
    translation = mat_np[:3, 3]

    return (coords @ mat_3x3.T) + translation


def apply_matrix_to_normals(normals: np.ndarray, matrix: Any) -> np.ndarray:
    """Apply rotation/scale to normals and re-normalize using vectorized logic."""
    mat_3x3 = np.array(matrix).reshape(4, 4)[:3, :3]
    new_normals = normals @ mat_3x3.T
    norms = np.linalg.norm(new_normals, axis=1, keepdims=True)

    return new_normals / np.where(norms > EPSILON, norms, 1.0)


def _is_vertex_group_used(
    ob: bpy.types.Object,
    vg: bpy.types.VertexGroup,
    vert_count: int,
    use_attr: bool,
) -> bool:
    """Helper for get_empty_vertex_group_indices: check if a group has weight."""
    if use_attr:
        attr = ob.data.attributes.get(vg.name)
        if attr and attr.domain == "POINT" and attr.data_type == "FLOAT":
            weights = np.empty(vert_count, dtype=np.float32)
            attr.data.foreach_get("value", weights)
            return bool(np.any(weights > EPSILON))

    # Fallback to slow iteration for old-style mesh data
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group == vg.index and g.weight > EPSILON:
                return True
    return False


def get_empty_vertex_group_indices(ob: bpy.types.Object) -> list[int]:
    """Identify indices of vertex groups that have no influence."""
    if not ob.data.vertices or not ob.vertex_groups:
        return []

    vert_count = len(ob.data.vertices)
    use_attr = hasattr(ob.data, "attributes")
    empty_indices = []

    for vg in ob.vertex_groups:
        if not _is_vertex_group_used(ob, vg, vert_count, use_attr):
            empty_indices.append(vg.index)

    return empty_indices


def smooth_deltas_tiled(
    deltas: np.ndarray,
    adj_map: np.ndarray,
    counts: np.ndarray,
    iterations: int,
    chunk_size: int = 10000,
) -> np.ndarray:
    """Smoothing pass tiled by vertex dimension to maximize L3 cache hits."""
    if iterations <= 0:
        return deltas

    key_count, vert_count, _ = deltas.shape
    max_valence = adj_map.shape[1]
    mask = (np.arange(max_valence) < counts).astype(np.float32).reshape(1, -1, max_valence, 1)

    src = deltas
    dst = np.empty_like(deltas)

    for _ in range(iterations):
        for v_start in range(0, vert_count, chunk_size):
            v_end = min(v_start + chunk_size, vert_count)

            chunk_adj = adj_map[v_start:v_end]
            chunk_counts = counts[v_start:v_end]
            chunk_mask = mask[:, v_start:v_end]

            neighbor_deltas = src[:, chunk_adj]
            sum_neighbors = np.sum(neighbor_deltas * chunk_mask, axis=2)
            mean_neighbors = sum_neighbors / chunk_counts

            dst[:, v_start:v_end] = (src[:, v_start:v_end] + mean_neighbors) / 2.0

        src, dst = dst, src

    return src


def get_adjacency(mesh: bpy.types.Mesh) -> tuple[np.ndarray, np.ndarray]:
    """Generate dense adjacency map for tensor smoothing using vectorized edge extraction."""
    vert_count = len(mesh.vertices)
    edge_count = len(mesh.edges)

    edge_verts = np.empty(edge_count * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", edge_verts)
    edge_verts.shape = (edge_count, 2)

    adj = [set() for _ in range(vert_count)]
    for u, v in edge_verts:
        adj[u].add(v)
        adj[v].add(u)

    counts = np.array([len(neighbors) for neighbors in adj], dtype=np.float32).reshape(-1, 1)
    max_valence = int(np.max(counts)) if adj else 0

    adj_map = np.zeros((vert_count, max_valence), dtype=np.int32, order="C")
    for i, neighbors in enumerate(adj):
        if neighbors:
            adj_map[i, : len(neighbors)] = list(neighbors)

    return adj_map, counts
