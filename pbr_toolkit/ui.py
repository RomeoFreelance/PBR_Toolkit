"""
ui.py — single "PBR Toolkit" parent panel + per-step sub-panels.
"""

import bpy
from bpy.types import Panel, UIList

from .core import naming, camera_contract

CATEGORY = "PBR Toolkit"


class PBRTK_UL_masks(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "path", text="", emboss=True)
        row.prop(item, "invert", text="", icon="MOD_MASK", toggle=True)


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
            layout.label(text=f"Base: {naming.resolve_base_name(s, context)}",
                         icon="MESH_DATA")
        else:
            layout.label(text="Select a mesh", icon="ERROR")


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
        layout.label(text="-> {base}_topview.png", icon="INFO")


class PBRTK_PT_masks(_ChildPanel):
    bl_label  = "2-3 · Segment & Masks to UV"
    bl_idname = "PBRTK_PT_masks"

    def draw(self, context):
        layout = self.layout
        s = context.scene.pbr_toolkit

        layout.label(text="2. External AI segmentation (SAM, ...):", icon="INFO")
        layout.label(text="   {base}_topview.png -> {base}_mask_N.png")
        layout.separator()

        layout.label(text="3. Reproject to UV:")
        layout.prop(s, "uv_resolution")
        layout.prop(s, "uv_padding")
        layout.prop(s, "camera_override")

        cam = s.camera_override or bpy.data.objects.get((s.camera_name or "").strip())
        if camera_contract.has_contract(cam):
            c = camera_contract.read(cam)
            layout.label(text=f"Camera OK -> mesh '{c.target_mesh}'", icon="CHECKMARK")
        else:
            layout.label(text="Run step 1 first (camera missing)", icon="ERROR")

        row = layout.row()
        row.scale_y = 1.4
        row.operator("pbrtk.masks_to_uv", icon="UV_DATA")


class PBRTK_PT_material(_ChildPanel):
    bl_label  = "4 · Setup Material"
    bl_idname = "PBRTK_PT_material"

    def draw(self, context):
        layout = self.layout
        s = context.scene.pbr_toolkit

        row = layout.row()
        row.scale_y = 1.4
        row.operator("pbrtk.setup_material", icon="NODETREE")

        # --- Overrides (empty = auto by convention) ---
        box = layout.box()
        box.label(text="Overrides (empty = auto by convention):", icon="FILE_TICK")
        box.prop(s, "tex_diffuse")
        box.prop(s, "tex_normal")
        box.prop(s, "tex_subsurface")
        box.prop(s, "tex_plate")

        box.separator()
        box.label(text="Zone masks:")
        row = box.row()
        row.template_list("PBRTK_UL_masks", "", s, "mask_overrides",
                          s, "mask_active_index", rows=3)
        col = row.column(align=True)
        col.operator("pbrtk.mask_add", icon="ADD", text="")
        col.operator("pbrtk.mask_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("pbrtk.mask_move", icon="TRIA_UP", text="").direction = "UP"
        col.operator("pbrtk.mask_move", icon="TRIA_DOWN", text="").direction = "DOWN"

        layout.separator()
        layout.label(text="Convention (when no override):", icon="INFO")
        col2 = layout.column(align=True)
        col2.scale_y = 0.7
        for line in (
            "{base}_diffuse.png   (required)",
            "{base}_normal.png    (required)",
            "{base}_mask_N_uv.png (zones)",
            "{base}_mask_plate_uv.png (coat)",
            "{base}_subsurface.png (optional)",
        ):
            col2.label(text=line)


classes = (
    PBRTK_UL_masks,
    PBRTK_PT_main,
    PBRTK_PT_render,
    PBRTK_PT_masks,
    PBRTK_PT_material,
)
