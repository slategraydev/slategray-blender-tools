# Slategray Blender Tools

This collection of high-performance tools handles complex mesh and rigging workflows in Blender that default tools often struggle with. The focus is on speed and data integrity, using NumPy to handle vertex data and modifier stacks efficiently.

## Core Features

### Apply Modifiers
This tool bakes modifiers while preserving shape keys. It uses NumPy vectorization to capture vertex coordinates across all shape states, wipes the modifier stack, and reconstructs the mesh and shape keys from the snapshots. This is essential for character pipelines where the stack must be flattened without losing facial expressions.

### Apply Rest Pose
This tool performs a one-click sync between a rig's pose and its rest state. It captures the mesh in its current deformed state, resets the armature's rest pose to match the current pose, and then re-applies the mesh data so nothing shifts.
