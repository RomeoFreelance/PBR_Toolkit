"""
ui.py — un panneau parent « PBR Toolkit » + sous-panneaux par étape.
"""

import bpy
from bpy.types import Panel

from .core import naming, camera_contract

CATEGORY = "PBR Toolkit"


class PBRTK_PT_main(Panel):
    bl_label       = "PBR Toolkit"
    bl_idname      = "PBRTK_PT_main"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = CATEGORY

    def draw(self, context):
        layout = self.layout
        s = context.scene.pbr_toolkit
        layout.prop(s, "project_folder")
        layout.prop(s, "base_name")

        obj = context.active_object
        if obj and obj.type == "MESH":
            layout.label(text=f"Base : {naming.resolve_base_name(s, context)}",
                         icon="MESH_DATA")
        else:
            layout.label(text="Sélectionner un mesh", icon="ERROR")


class _ChildPanel(Panel):
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = CATEGORY
    bl_parent_id   = "PBRTK_PT_main"
    bl_options     = {"DEFAULT_CLOSED"}


class PBRTK_PT_render(_ChildPanel):
    bl_label  = "1 · Render Top View"
    bl_idname = "PBRTK_PT_render"

    def draw(self, context):
        layout = self.layout
        s = context.scene.pbr_toolkit
        layout.prop(s, "render_resolution")
        layout.prop(s, "camera_name")
        row = layout.row()
        row.scale_y = 1.4
        row.operator("pbrtk.render_topview", icon="RENDER_STILL")
        layout.label(text="→ {base}_topview.png", icon="INFO")


class PBRTK_PT_masks(_ChildPanel):
    bl_label  = "2-3 · Segment & Masks to UV"
    bl_idname = "PBRTK_PT_masks"

    def draw(self, context):
        layout = self.layout
        s = context.scene.pbr_toolkit

        layout.label(text="2. Segmentation IA externe (SAM…) :", icon="INFO")
        layout.label(text="   {base}_topview.png → {base}_mask_N.png")
        layout.separator()

        layout.label(text="3. Reprojection vers UV :")
        layout.prop(s, "uv_resolution")
        layout.prop(s, "uv_padding")

        cam = bpy.data.objects.get((s.camera_name or "").strip())
        if camera_contract.has_contract(cam):
            c = camera_contract.read(cam)
            layout.label(text=f"Caméra OK → mesh « {c.target_mesh} »", icon="CHECKMARK")
        else:
            layout.label(text="Lance d'abord l'étape 1 (caméra manquante)", icon="ERROR")

        row = layout.row()
        row.scale_y = 1.4
        row.operator("pbrtk.masks_to_uv", icon="UV_DATA")


class PBRTK_PT_material(_ChildPanel):
    bl_label  = "4 · Setup Material"
    bl_idname = "PBRTK_PT_material"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.4
        row.operator("pbrtk.setup_material", icon="NODETREE")

        layout.separator()
        layout.label(text="Textures attendues (espace UV) :", icon="INFO")
        col = layout.column(align=True)
        col.scale_y = 0.7
        for line in (
            "{base}_diffuse.png   (requis)",
            "{base}_normal.png    (requis)",
            "{base}_mask_N_uv.png (zones)",
            "{base}_mask_plate_uv.png (coat)",
            "{base}_subsurface.png (option)",
        ):
            col.label(text=line)


classes = (
    PBRTK_PT_main,
    PBRTK_PT_render,
    PBRTK_PT_masks,
    PBRTK_PT_material,
)
