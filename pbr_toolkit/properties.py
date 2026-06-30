"""
properties.py — modèle de données unique : scene.pbr_toolkit (PBRTK_Settings).

Principe des overrides : chaque champ est optionnel ; vide = auto-détection par
convention de nommage (voir core/naming.py).
"""

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    StringProperty, EnumProperty, IntProperty, BoolProperty,
    CollectionProperty, PointerProperty,
)


_RENDER_RES = [
    ("1024", "1K — 1024px", ""),
    ("2048", "2K — 2048px (recommandé)", ""),
    ("4096", "4K — 4096px", ""),
]

_UV_RES = [
    ("1024", "1K", ""),
    ("2048", "2K", ""),
    ("4096", "4K (recommandé)", ""),
    ("8192", "8K", ""),
]


def _camera_poll(self, obj):
    return obj.type == "CAMERA"


class PBRTK_MaskItem(PropertyGroup):
    """Un masque de zone (override manuel)."""
    path: StringProperty(
        name="Masque",
        description="Fichier masque espace-UV pour cette zone",
        subtype="FILE_PATH",
    )
    invert: BoolProperty(
        name="Inverser",
        description="Inverse le masque avant utilisation",
        default=False,
    )


class PBRTK_Settings(PropertyGroup):
    # --- Communs ---
    project_folder: StringProperty(
        name="Dossier projet",
        description="Dossier unique contenant rendus, masques et textures de l'asset",
        subtype="DIR_PATH",
        default="",
    )
    base_name: StringProperty(
        name="Nom de base",
        description="Préfixe des fichiers ({base}_*). Vide = nom du mesh actif.",
        default="",
    )
    camera_name: StringProperty(
        name="Nom caméra",
        description="Caméra ortho persistante (contrat étape 1 → 3)",
        default="PBRTK_TopView_Cam",
    )

    # --- Étape 1 ---
    render_resolution: EnumProperty(
        name="Résolution rendu", items=_RENDER_RES, default="2048",
    )

    # --- Étape 3 ---
    uv_resolution: EnumProperty(
        name="Résolution UV", items=_UV_RES, default="4096",
    )
    uv_padding: IntProperty(
        name="Padding UV (px)",
        description="Edge padding contre les cracks aux seams UV (0 = désactivé)",
        default=4, min=0, max=32,
    )
    camera_override: PointerProperty(
        name="Caméra (override)",
        description="Caméra de contrat à utiliser. Vide = résolue par 'Nom caméra'.",
        type=bpy.types.Object,
        poll=_camera_poll,
    )

    # --- Étape 4 : overrides textures (vide = auto par convention) ---
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
