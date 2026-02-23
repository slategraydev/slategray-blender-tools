# ------------------------------------------------------------------------------
# Copyright (c) 2026 Randall Rosas (Slategray)
# ------------------------------------------------------------------------------

"""Package initialization for Slategray Blender Tools utilities."""

from .lifecycle import (
    register_modules as register_modules,
)
from .lifecycle import (
    unregister_modules as unregister_modules,
)
from .mesh import (
    bake_mesh_operation as bake_mesh_operation,
)
from .mesh import (
    capture_mesh_snapshot as capture_mesh_snapshot,
)
from .mesh import (
    extract_mesh_data as extract_mesh_data,
)
from .mesh import (
    get_modifier_snapshot as get_modifier_snapshot,
)
from .mesh import (
    restore_object as restore_object,
)
from .performance import (
    apply_matrix_numpy as apply_matrix_numpy,
)
from .performance import (
    apply_matrix_to_normals as apply_matrix_to_normals,
)
from .performance import (
    get_adjacency as get_adjacency,
)
from .performance import (
    get_empty_vertex_group_indices as get_empty_vertex_group_indices,
)
from .performance import (
    smooth_deltas_tiled as smooth_deltas_tiled,
)
from .rigging import (
    apply_armature_rest_pose as apply_armature_rest_pose,
)
