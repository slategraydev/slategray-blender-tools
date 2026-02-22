# Apply Modifiers (v1.0.0)

A high-performance Blender addon designed to bake modifiers into a mesh while preserving all shape key data. Optimized for **Blender 5.0+** using NumPy vectorization and advanced dependency graph management.

## Features

- **High-Performance Extraction**: Features an $O(N)$ shape key extraction algorithm that minimizes RNA property overhead.
- **Efficient Updates**: Uses targeted dependency graph updates instead of full scene evaluations to maximize speed in complex scenes.
- **Multi-Object Support**: Batch-process modifiers across multiple selected mesh objects with individual selection control.
- **Vectorized Performance**: Uses C-level data transfer via NumPy to bypass Python interpreter bottlenecks.
- **Shape Key Preservation**: Bakes the modifier stack while maintaining all shape key geometry, names, relative references, and vertex groups.
- **Topology Safety**: Automatically verifies vertex count consistency across shape key states during evaluation.
- **Selective Baking**: Choose exactly which modifiers to bake from the stack per object.
- **Safety Warnings**: Detects and warns when Armatures are selected to prevent accidental pose baking.

## Installation

1. Download `ApplyModifiers.py`.
2. In Blender, go to `Edit > Preferences > Add-ons > Install...`.
3. Select the file and enable **Object: Apply Modifiers**.

## Usage

1. Select one or more mesh objects with modifiers and shape keys.
2. Locate the tool in the **Sidebar (N-panel) > Tool > Apply Modifiers**.
3. Alternatively, find it in the **Object Context Menu** (Right-Click in Object Mode).
4. In the popup dialogue, toggle the modifiers you wish to bake for each selected object.
5. Click **Apply Modifiers**.

## Development

This project uses modern Python tooling for code quality:
- **Ruff**: For linting and formatting.
- **Basedpyright**: For static type checking with Blender API stubs.

To set up the development environment:
```powershell
pip install -r dev-requirements.txt
```

## License

Copyright (c) 2026 Randall Rosas (Slategray).  
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
