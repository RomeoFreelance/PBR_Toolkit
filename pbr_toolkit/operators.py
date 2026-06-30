"""
operators.py — opérateurs fins déléguant au noyau (pbr_toolkit.core).
"""

import os
import bpy
from bpy.types import Operator

from .core import render, reproject, material, naming


class PBRTK_OT_RenderTopView(Operator):
    bl_idname      = "pbrtk.render_topview"
    bl_label       = "Render Top View"
    bl_description = "Rendu orthographique top-view (passe DiffCol) pour segmentation"
    bl_options     = {"REGISTER"}

    def execute(self, context):
        ok, msg = render.render_topview(context, context.scene.pbr_toolkit)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


class PBRTK_OT_MasksToUV(Operator):
    bl_idname      = "pbrtk.masks_to_uv"
    bl_label       = "Reproject Masks to UV"
    bl_description = "Reprojette les masques espace-image vers l'espace UV"
    bl_options     = {"REGISTER"}

    def execute(self, context):
        ok, msg = reproject.reproject_all(context, context.scene.pbr_toolkit)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


class PBRTK_OT_SetupMaterial(Operator):
    bl_idname      = "pbrtk.setup_material"
    bl_label       = "Setup Material"
    bl_description = "Construit le node graph PBR à partir des textures UV"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.pbr_toolkit
        folder = bpy.path.abspath(settings.project_folder)
        if not folder or not os.path.isdir(folder):
            self.report({"ERROR"}, "Dossier projet invalide.")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Sélectionner un mesh.")
            return {"CANCELLED"}

        base = naming.resolve_base_name(settings, context)
        if not base:
            self.report({"ERROR"}, "Nom de base introuvable.")
            return {"CANCELLED"}

        ok, msg = material.build_material(obj, folder, base)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


classes = (
    PBRTK_OT_RenderTopView,
    PBRTK_OT_MasksToUV,
    PBRTK_OT_SetupMaterial,
)
