"""
properties.py — single data model: scene.pbr_toolkit (PBRTK_Settings).

Override principle: every field is optional; empty = auto-detection via the
naming convention (see core/naming.py).
"""

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    StringProperty, EnumProperty, IntProperty, BoolProperty,
    CollectionProperty, PointerProperty,
)


_RENDER_RES = [
    ("1024", "1K — 1024px", ""),
    ("2048", "2K — 2048px (recommended)", ""),
    ("4096", "4K — 4096px", ""),
]

_UV_RES = [
    ("1024", "1K", ""),
    ("2048", "2K", ""),
    ("4096", "4K (recommended)", ""),
    ("8192", "8K", ""),
]


def _camera_poll(self, obj):
    return obj.type == "CAMERA"


class PBRTK_MaskItem(PropertyGroup):
    """A zone mask (manual override)."""
    path: StringProperty(
        name="Mask",
        description="UV-space mask file for this zone",
        subtype="FILE_PATH",
    )
    invert: BoolProperty(
        name="Invert",
        description="Invert the mask before use",
        default=False,
    )


class PBRTK_Settings(PropertyGroup):
    # --- Common ---
    project_folder: StringProperty(
        name="Project folder",
        description="Single folder holding the asset's renders, masks and textures",
        subtype="DIR_PATH",
        default="",
    )
    base_name: StringProperty(
        name="Base name",
        description="File prefix ({base}_*). Empty = active mesh name.",
        default="",
    )
    camera_name: StringProperty(
        name="Camera name",
        description="Persistent ortho camera (contract step 1 -> 3)",
        default="PBRTK_TopView_Cam",
    )

    # --- Step 1 ---
    render_resolution: EnumProperty(
        name="Render resolution", items=_RENDER_RES, default="2048",
    )

    # --- Step 3 ---
    uv_resolution: EnumProperty(
        name="UV resolution", items=_UV_RES, default="4096",
    )
    uv_padding: IntProperty(
        name="UV padding (px)",
        description="Edge padding to avoid cracks at UV seams (0 = disabled)",
        default=4, min=0, max=32,
    )
    camera_override: PointerProperty(
        name="Camera (override)",
        description="Contract camera to use. Empty = resolved by 'Camera name'.",
        type=bpy.types.Object,
        poll=_camera_poll,
    )

    # --- Step 4: texture overrides (empty = auto by convention) ---
    tex_diffuse: StringProperty(name="Diffuse (override)", subtype="FILE_PATH")
    tex_normal: StringProperty(name="Normal (override)", subtype="FILE_PATH")
    tex_subsurface: StringProperty(name="Subsurface (override)", subtype="FILE_PATH")
    tex_plate: StringProperty(name="Plate mask (override)", subtype="FILE_PATH")

    mask_overrides: CollectionProperty(type=PBRTK_MaskItem)
    mask_active_index: IntProperty(default=0)


classes = (
    PBRTK_MaskItem,
    PBRTK_Settings,
)
