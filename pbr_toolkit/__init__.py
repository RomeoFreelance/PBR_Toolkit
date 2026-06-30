# pbr_toolkit/__init__.py
# Addon Blender — PBR Toolkit : workflow capture top-view → material PBR.
#
#   Étape 1 : Render Top View  (albédo ortho, passe DiffCol Cycles)
#   Étape 2 : Segmentation IA  (externe → masques espace-image)
#   Étape 3 : Masks to UV       (reprojection des masques vers l'espace UV)
#   Étape 4 : Setup Material    (node graph PBR ajustable)
#
# Architecture en couches :
#   properties.py  modèle de données unique (scene.pbr_toolkit)
#   operators.py   opérateurs fins
#   ui.py          panneau parent + sous-panneaux
#   core/          logique métier (naming, camera_contract, image_io,
#                  render, reproject, material)

bl_info = {
    "name": "PBR Toolkit",
    "author": "Custom Pipeline",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > PBR Toolkit",
    "description": "Capture top-view, reprojection de masques vers UV, "
                   "et setup de material PBR ajustable.",
    "category": "Material",
}

import bpy
from bpy.props import PointerProperty

from . import properties
from . import operators
from . import ui

_classes = (
    properties.PBRTK_Settings,
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
