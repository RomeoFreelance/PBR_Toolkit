# PBR Toolkit

A Blender add-on to texture objects captured top-down (photogrammetry, flat
scans, any asset). It covers the whole chain: rendering the albedo seen from
above, reprojecting AI-generated masks into UV space, and building an
adjustable multi-zone PBR material.

> Blender **4.0+** · **Cycles** required for the render step.

---

## Workflow

```
┌─────────────────┐   ┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐
│ 1. Render Top   │   │ 2. Segment   │   │ 3. Masks to UV  │   │ 4. Setup Material│
│    View         │ → │   (AI, ext.) │ → │                 │ → │                  │
│ ortho albedo    │   │ image-space  │   │ reprojection    │   │ adjustable PBR   │
│ + persistent    │   │ masks        │   │ image → UV      │   │ node graph       │
│ ortho camera    │   │              │   │                 │   │                  │
└─────────────────┘   └──────────────┘   └─────────────────┘   └──────────────────┘
```

Everything lives in **a single project folder** and revolves around a **base
name** (the active mesh name by default). The backbone is the **persistent
ortho camera** created in step 1: it stores, as custom properties (`pbrtk_*`),
the geometric contract (target mesh, center, extent, resolution) that step 3
reads back to reproject without error.

### Step 1 — Render Top View
Orthographic top-down render via the **DiffCol** pass (Cycles, 1 sample): the
"flat" albedo without shading. Creates/reuses a named ortho camera framed
automatically on the selected mesh's bounding box.
→ `{base}_topview.png`

### Step 2 — AI Segmentation (external)
Outside Blender: segment the top-view render (e.g. SAM) to produce one binary
mask per zone, in the render's image space.
→ `{base}_mask_1.png`, `{base}_mask_2.png`, … (optionally
`{base}_mask_plate.png`)

### Step 3 — Masks to UV
Reprojects **all** image-space masks of the asset (numbered + plate) into the
mesh UV space. Vectorized inverse reprojection (NumPy) on the **evaluated mesh**
(modifiers applied), consistent with the render. Optional *edge padding* against
seam cracks.
→ `{base}_mask_1_uv.png`, … (`_uv` suffix added)

### Step 4 — Setup Material
Builds a **PBRToolkit_Controls** node group (HSV, normal map, bump, per-zone
Roughness/Specular/Subsurface chains) wired into a Principled BSDF. The material
consumes the **UV-space** masks (`_uv`). Per-zone adjustment sliders are exposed
on the group.

**Overrides:** every input can be overridden manually (file pickers for
diffuse/normal/subsurface/plate, plus a dynamic zone-mask list with a per-mask
invert toggle). Leave a field empty to fall back to the naming convention.

---

## Installation

1. Download/clone this repository.
2. Zip the **`pbr_toolkit/`** folder (the zip must contain the `pbr_toolkit/`
   folder at its root, not its loose contents).
3. Blender › `Edit > Preferences > Add-ons > Install…` › select the zip.
4. Enable **"PBR Toolkit"**. The tab appears in the 3D View N-Panel.

---

## Naming convention

All files of an asset share the `{base}` prefix (the base name, the mesh name
by default), inside the **project folder**:

| File                         | Space  | Role                                   |
| ---------------------------- | ------ | -------------------------------------- |
| `{base}_diffuse.png`         | UV     | albedo / base color (**required**)     |
| `{base}_normal.png`          | UV     | tangent-space normal map (**required**)|
| `{base}_subsurface.png`      | UV     | subsurface map (optional)              |
| `{base}_topview.png`         | image  | top-view render (step 1 output)        |
| `{base}_mask_N.png`          | image  | zone mask (step 2)                     |
| `{base}_mask_plate.png`      | image  | plate mask → Coat (step 2, optional)   |
| `{base}_mask_*_uv.png`       | UV     | reprojected mask (step 3 → material)   |
| `..._inv...`                 |        | pre-inverted variant                   |

Step 3 reprojects the image-space `_mask_*` (without `_uv`); the material only
consumes the `_uv` ones.

---

## Repository layout

```
pbr_toolkit/
├── __init__.py          bl_info + single register()
├── properties.py        single data model (scene.pbr_toolkit)
├── operators.py         3 thin operators → delegate to the core
├── ui.py                1 parent panel + 3 sub-panels
└── core/                business logic (no Blender classes)
    ├── naming.py            naming convention {base}_* (single source)
    ├── camera_contract.py   pbrtk_* contract on the camera (single source)
    ├── image_io.py          shared foreach_get/set image I/O
    ├── render.py            top-view DiffCol render
    ├── reproject.py         mask → UV reprojection
    └── material.py          node group + material
```

---

## License

[MIT](LICENSE) © Romeo Ducos.
