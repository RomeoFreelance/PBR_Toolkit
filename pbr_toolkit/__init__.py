# pbr_toolkit/__init__.py
# Blender add-on — PBR Toolkit: top-view capture -> PBR material workflow.
#
#   Step 1: Render Top View  (ortho albedo, Cycles DiffCol pass)
#   Step 2: AI Segmentation  (external -> image-space masks)
#   Step 3: Masks to UV       (reproject masks into UV space)
#   Step 4: Setup Material    (adjustable PBR node graph)
#
# Layered architecture:
#   properties.py  single data model (scene.pbr_toolkit)
#   operators.py   thin operators
#   ui.py          parent panel + sub-panels
#   core/          business logic (naming, camera_contract, image_io,
#                  render, reproject, material)

bl_info = {
    "name": "PBR Toolkit",
    "author": "Romeo Ducos",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > PBR Toolkit",
    "description": "Top-view capture, mask reprojection to UV, and adjustable "
                   "PBR material setup.",
    "category": "Material",
}

import bpy
from bpy.props import PointerProperty

from . import properties
from . import operators
from . import ui

_classes = (
    *properties.classes,
    *operators.classes,
    *ui.classes,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pbr_toolkit = PointerProperty(type=properties.PBRTK_Settings)


def unregister():
    del bpy.types.Scene.pbr_toolkit
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
