"""
operators.py — thin operators delegating to the core (pbr_toolkit.core).
"""

import os
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from .core import render, reproject, material, naming


def resolve_textures(settings, folder, base):
    """
    Material textures: auto-detected by convention, then overridden field by
    field by any set override. A non-empty mask list fully overrides the zone
    masks.
    """
    tex = naming.find_uv_textures(folder, base)

    def ap(p):
        return bpy.path.abspath(p) if p else ""

    if settings.tex_diffuse:
        tex["diffuse"] = ap(settings.tex_diffuse)
    if settings.tex_normal:
        tex["normal"] = ap(settings.tex_normal)
    if settings.tex_subsurface:
        tex["subsurface"] = ap(settings.tex_subsurface)
    if settings.tex_plate:
        tex["mask_plate"] = ap(settings.tex_plate)

    items = [it for it in settings.mask_overrides if it.path]
    if items:
        tex["masks"] = [(ap(it.path), it.invert, i) for i, it in enumerate(items, 1)]

    return tex


class PBRTK_OT_RenderTopView(Operator):
    bl_idname      = "pbrtk.render_topview"
    bl_label       = "Render Top View"
    bl_description = "Orthographic top-view render (DiffCol pass) for segmentation"
    bl_options     = {"REGISTER"}

    def execute(self, context):
        ok, msg = render.render_topview(context, context.scene.pbr_toolkit)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


class PBRTK_OT_MasksToUV(Operator):
    bl_idname      = "pbrtk.masks_to_uv"
    bl_label       = "Reproject Masks to UV"
    bl_description = "Reproject image-space masks into UV space"
    bl_options     = {"REGISTER"}

    def execute(self, context):
        ok, msg = reproject.reproject_all(context, context.scene.pbr_toolkit)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


class PBRTK_OT_SetupMaterial(Operator):
    bl_idname      = "pbrtk.setup_material"
    bl_label       = "Setup Material"
    bl_description = "Build the PBR node graph from the UV textures"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.pbr_toolkit
        folder = bpy.path.abspath(settings.project_folder)
        if not folder or not os.path.isdir(folder):
            self.report({"ERROR"}, "Invalid project folder.")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh.")
            return {"CANCELLED"}

        base = naming.resolve_base_name(settings, context)
        if not base:
            self.report({"ERROR"}, "Could not resolve base name.")
            return {"CANCELLED"}

        try:
            tex = resolve_textures(settings, folder, base)
            ok, msg = material.build_material(obj, tex, base)
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, str(e)

        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


# --- Mask list management (override) ---

class PBRTK_OT_MaskAdd(Operator):
    bl_idname  = "pbrtk.mask_add"
    bl_label   = "Add mask"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.pbr_toolkit
        s.mask_overrides.add()
        s.mask_active_index = len(s.mask_overrides) - 1
        return {"FINISHED"}


class PBRTK_OT_MaskRemove(Operator):
    bl_idname  = "pbrtk.mask_remove"
    bl_label   = "Remove mask"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.pbr_toolkit
        if s.mask_overrides:
            s.mask_overrides.remove(s.mask_active_index)
            s.mask_active_index = max(0, min(s.mask_active_index, len(s.mask_overrides) - 1))
        return {"FINISHED"}


class PBRTK_OT_MaskMove(Operator):
    bl_idname  = "pbrtk.mask_move"
    bl_label   = "Move mask"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        s = context.scene.pbr_toolkit
        i = s.mask_active_index
        n = len(s.mask_overrides)
        if n < 2:
            return {"CANCELLED"}
        j = i - 1 if self.direction == "UP" else i + 1
        if 0 <= j < n:
            s.mask_overrides.move(i, j)
            s.mask_active_index = j
        return {"FINISHED"}


classes = (
    PBRTK_OT_RenderTopView,
    PBRTK_OT_MasksToUV,
    PBRTK_OT_SetupMaterial,
    PBRTK_OT_MaskAdd,
    PBRTK_OT_MaskRemove,
    PBRTK_OT_MaskMove,
)
