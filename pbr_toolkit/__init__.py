# pbr_toolkit/__init__.py
# Addon Blender unifie - PBR Toolkit (workflow capture top-view -> material) :
#   Etape 1 : Render Top View  (albedo ortho, passe DiffCol Cycles)
#   Etape 2 : SAM segment       (script externe -> masques image-space)
#   Etape 3 : Masks to UV        (reprojection des masques vers l'espace UV)
#   Etape 4 : Setup Material     (node graph PBR ajustable)
#
# Les trois etapes Blender partagent le meme onglet N-Panel "PBR Toolkit" et la
# meme convention de nommage {dish}_*.png. La camera ortho persistante creee a
# l'etape 1 sert de contrat (cx, cy, extent, resolution) pour l'etape 3.

bl_info = {
    "name": "PBR Toolkit",
    "author": "Custom Pipeline",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > PBR Toolkit",
    "description": "Render top-view, reprojection des masques SAM vers UV, "
                   "et setup du material PBR - tout-en-un.",
    "category": "Material",
}

from . import render_topview
from . import masks_to_uv
from . import setup_material

# Ordre d'enregistrement = ordre logique du workflow.
_modules = (render_topview, masks_to_uv, setup_material)


def register():
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
