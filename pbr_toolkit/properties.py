"""
properties.py — modèle de données unique : scene.pbr_toolkit (PBRTK_Settings).
"""

from bpy.types import PropertyGroup
from bpy.props import StringProperty, EnumProperty, IntProperty


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


class PBRTK_Settings(PropertyGroup):
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
    render_resolution: EnumProperty(
        name="Résolution rendu",
        items=_RENDER_RES,
        default="2048",
    )
    uv_resolution: EnumProperty(
        name="Résolution UV",
        items=_UV_RES,
        default="4096",
    )
    uv_padding: IntProperty(
        name="Padding UV (px)",
        description="Edge padding contre les cracks aux seams UV (0 = désactivé)",
        default=4, min=0, max=32,
    )
