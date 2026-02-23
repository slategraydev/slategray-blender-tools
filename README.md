# Slategray Blender Tools

These are a few high-performance utilities I built to handle some of the more tedious parts of mesh and rigging pipelines. They're designed to be fast, reliable, and straightforward, mostly so I can spend less time fixing broken modifier stacks and more time actually finishing projects.

## Core Features

### Apply Modifiers
Bake your modifiers without losing your shape keys. It uses NumPy to snapshot vertex coordinates across every shape state, clears the stack, and puts it all back together. It's a clean way to flatten a character pipeline while keeping your facial expressions intact.

### Transfer Shape Keys
A fast way to map shape keys from a body to clothing. It uses KD-Trees for `O(log n)` vertex lookups and vectorized smoothing to prevent clipping issues. It’s built to handle complex topology mapping without much fuss.

### Clean Vertex Groups
A simple utility to find and remove vertex groups that aren't actually influencing anything. It scans the mesh data quickly so you don't have to manually clean up hundreds of empty groups.

### Apply Rest Pose
One-click sync for a rig’s rest pose and its current state. It snapshots the mesh data, resets the armature’s rest pose, and re-applies the coordinates so nothing shifts. It saves a lot of manual re-rigging.

## Technical Details
- **NumPy & SIMD:** I used cache-aligned buffers and vectorized operations for matrix math and 4D tensor smoothing. Python loops are too slow for high-poly work, so this handles the heavy lifting in C-speed.
- **Spatial Partitioning:** Uses `mathutils.kdtree` for efficient nearest-neighbor mapping between different meshes.
- **Tiled Smoothing:** The smoothing passes are tiled to maximize L3 cache hits. It’s faster and more efficient on the CPU.
- **Stability:** Everything is strictly typed and run through `Basedpyright` and `Ruff`. I’d rather catch a bug in the linter than deal with a crash later.

## Installation
1. Download the ZIP.
2. `Edit` > `Preferences` > `Add-ons` > `Install`.
3. Enable **Slategray Blender Tools**.

## Usage
Look in the Sidebar (`N` panel) under the **SLATE** tab. 
Everything is right there.
