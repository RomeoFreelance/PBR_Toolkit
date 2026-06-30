"""
masks_to_uv.py
==============
Etape 3 -- Reprojection des masques SAM (image-space) vers l'espace UV du
mesh, via une camera ortho top-down (contrat avec render_topview).

Algo : reprojection inverse. Pour chaque triangle du mesh, on rasterise
dans l'espace UV de sortie ; pour chaque texel UV on calcule sa position
world via barycentriques, puis on projette sur l'image source via les
params de la camera ortho (cx, cy, extent, resolution). Pas de raycasting,
pas de trous, vectorise NumPy.

La geometrie utilisee est le mesh EVALUE (modifiers appliques), pour rester
coherent avec ce qui a ete rendu par render_topview.
"""

import bpy
import os
import re
import glob
import numpy as np
from bpy.props import StringProperty, EnumProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup


UV_RES_ITEMS = [
    ("1024", "1K", ""),
    ("2048", "2K", ""),
    ("4096", "4K (recommande)", ""),
    ("8192", "8K", ""),
]

# Masques numerotes uniquement (_mask_1, _mask_2, ...), pas _mask_plate.
MASK_INDEX_RE = re.compile(r"_mask_(\d+)", re.IGNORECASE)


def cam_poll(self, obj):
    return obj.type == "CAMERA" and "sam_target_mesh" in obj


def load_mask_grayscale(path):
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        if w == 0 or h == 0:
            return None, 0, 0
        # foreach_get : lecture native rapide (vs marshalling Python de
        # img.pixels[:], prohibitif en 4K/8K).
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        px = buf.reshape(h, w, 4)
        gray = px[:, :, 0]  # masque N&B : R=G=B
        # Blender charge bottom-up, on flip pour avoir y=0 en haut
        gray = np.ascontiguousarray(np.flipud(gray))
        return gray, w, h
    finally:
        bpy.data.images.remove(img)


def reproject_mask(mesh, mw, mask_img, cam_params, uv_res):
    """
    Reprojette un masque image-space vers une texture UV.
    `mesh` est un Mesh deja triangule (calc_loop_triangles) et `mw` sa
    matrice world. Retourne un array (uv_res, uv_res) float32 dans [0, 1].
    """
    cx      = cam_params["cx"]
    cy      = cam_params["cy"]
    extent  = cam_params["extent"]
    src_res = mask_img.shape[0]  # masque carre

    out = np.zeros((uv_res, uv_res), dtype=np.float32)
    uv_layer = mesh.uv_layers.active.data

    for tri in mesh.loop_triangles:
        # Sommets world-space
        v0 = mw @ mesh.vertices[tri.vertices[0]].co
        v1 = mw @ mesh.vertices[tri.vertices[1]].co
        v2 = mw @ mesh.vertices[tri.vertices[2]].co
        # UVs
        uv0 = uv_layer[tri.loops[0]].uv
        uv1 = uv_layer[tri.loops[1]].uv
        uv2 = uv_layer[tri.loops[2]].uv

        # UV en pixels (origine bas-gauche conservee, on flip Y a la fin)
        u0p, v0p = uv0.x * uv_res, uv0.y * uv_res
        u1p, v1p = uv1.x * uv_res, uv1.y * uv_res
        u2p, v2p = uv2.x * uv_res, uv2.y * uv_res

        # Bbox UV
        u_min = max(int(np.floor(min(u0p, u1p, u2p))), 0)
        u_max = min(int(np.ceil (max(u0p, u1p, u2p))), uv_res - 1)
        v_min = max(int(np.floor(min(v0p, v1p, v2p))), 0)
        v_max = min(int(np.ceil (max(v0p, v1p, v2p))), uv_res - 1)
        if u_max < u_min or v_max < v_min:
            continue

        # Grille de texels dans la bbox
        us, vs = np.meshgrid(
            np.arange(u_min, u_max + 1) + 0.5,
            np.arange(v_min, v_max + 1) + 0.5,
            indexing="xy",
        )

        # Barycentriques 2D dans l'espace UV
        denom = (v1p - v2p) * (u0p - u2p) + (u2p - u1p) * (v0p - v2p)
        if abs(denom) < 1e-12:
            continue
        b0 = ((v1p - v2p) * (us - u2p) + (u2p - u1p) * (vs - v2p)) / denom
        b1 = ((v2p - v0p) * (us - u2p) + (u0p - u2p) * (vs - v2p)) / denom
        b2 = 1.0 - b0 - b1

        inside = (b0 >= 0) & (b1 >= 0) & (b2 >= 0)
        if not np.any(inside):
            continue

        # Position world des texels valides
        wx = b0 * v0.x + b1 * v1.x + b2 * v2.x
        wy = b0 * v0.y + b1 * v1.y + b2 * v2.y

        # Projection ortho world -> pixel image source
        px = ((wx - cx) / extent + 0.5) * src_res
        py = ((cy - wy) / extent + 0.5) * src_res  # Y inverse (image top-down)
        ix = np.clip(px.astype(np.int32), 0, src_res - 1)
        iy = np.clip(py.astype(np.int32), 0, src_res - 1)

        # Lecture nearest neighbor (masque binaire)
        vals = mask_img[iy, ix]

        # Ecriture (Y UV flip pour avoir origine top-left a la sauvegarde)
        out_y = uv_res - 1 - (v_min + np.arange(vs.shape[0]))
        out_y_grid = np.repeat(out_y[:, None], us.shape[1], axis=1)
        out_x_grid = np.repeat((u_min + np.arange(us.shape[1]))[None, :],
                               vs.shape[0], axis=0)

        sel_y = out_y_grid[inside]
        sel_x = out_x_grid[inside]
        out[sel_y, sel_x] = np.maximum(out[sel_y, sel_x], vals[inside])

    return out


def dilate_uv(arr, iterations=4):
    """
    Edge padding : etend les valeurs non-nulles sur les texels voisins vides.
    Evite les cracks aux seams UV lors du filtrage de texture.
    """
    out = arr.copy()
    for _ in range(iterations):
        empty = out == 0.0
        if not np.any(empty):
            break
        up    = np.roll(out, -1, axis=0)
        down  = np.roll(out,  1, axis=0)
        left  = np.roll(out, -1, axis=1)
        right = np.roll(out,  1, axis=1)
        neighbors_max = np.maximum(np.maximum(up, down), np.maximum(left, right))
        out = np.where(empty, neighbors_max, out)
    return out


def save_uv_png(arr, path):
    h, w = arr.shape
    rgba = np.empty((h, w, 4), dtype=np.float32)
    rgba[:, :, 0] = arr
    rgba[:, :, 1] = arr
    rgba[:, :, 2] = arr
    rgba[:, :, 3] = 1.0
    img = bpy.data.images.new(
        name="__masks_to_uv_tmp__",
        width=w, height=h, alpha=False, float_buffer=False,
    )
    try:
        # Blender stocke bottom-up, on flip. foreach_set : ecriture native.
        flat = np.ascontiguousarray(np.flipud(rgba).ravel(), dtype=np.float32)
        img.pixels.foreach_set(flat)
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


class PBRTK_OT_MasksToUV(Operator):
    bl_idname      = "pbrtk.masks_to_uv"
    bl_label       = "Reproject Masks to UV"
    bl_description = "Reprojette les masques SAM vers l'espace UV via la camera"
    bl_options     = {"REGISTER"}

    def execute(self, context):
        props = context.scene.pbrtk_m2uv_props
        cam   = props.camera
        if not cam or "sam_target_mesh" not in cam:
            self.report({"ERROR"}, "Camera invalide (pas de custom prop sam_target_mesh).")
            return {"CANCELLED"}

        mesh_name = cam["sam_target_mesh"]
        mesh_obj  = bpy.data.objects.get(mesh_name)
        if not mesh_obj or mesh_obj.type != "MESH":
            self.report({"ERROR"}, f"Mesh '{mesh_name}' introuvable.")
            return {"CANCELLED"}

        in_folder  = bpy.path.abspath(props.input_folder)
        out_folder = bpy.path.abspath(props.output_folder)
        if not os.path.isdir(in_folder) or not os.path.isdir(out_folder):
            self.report({"ERROR"}, "Dossiers invalides.")
            return {"CANCELLED"}

        # Masques numerotes uniquement, tries par index numerique (pas
        # alphabetique : _mask_10 apres _mask_9). Le plate-mask est exclu.
        pattern = os.path.join(in_folder, f"{mesh_name}_mask_*.png")
        indexed = []
        for mp in glob.glob(pattern):
            m = MASK_INDEX_RE.search(os.path.basename(mp))
            if m:
                indexed.append((int(m.group(1)), mp))
        indexed.sort(key=lambda t: t[0])
        masks = [mp for _, mp in indexed]
        if not masks:
            self.report({"ERROR"}, f"Aucun masque numerote trouve : {pattern}")
            return {"CANCELLED"}

        cam_params = {
            "cx":     float(cam["sam_center_x"]),
            "cy":     float(cam["sam_center_y"]),
            "extent": float(cam["sam_extent"]),
        }
        uv_res = int(props.uv_resolution)

        # Mesh evalue (modifiers appliques) -> coherent avec le rendu top-view.
        # Evalue + triangule une seule fois pour tous les masques.
        deps      = context.evaluated_depsgraph_get()
        obj_eval  = mesh_obj.evaluated_get(deps)
        mesh_eval = obj_eval.to_mesh()
        try:
            if not mesh_eval.uv_layers.active:
                raise RuntimeError("Le mesh n'a pas de UV map active.")
            mesh_eval.calc_loop_triangles()
            mw = obj_eval.matrix_world.copy()

            for i, mp in enumerate(masks, 1):
                name = os.path.splitext(os.path.basename(mp))[0]
                self.report({"INFO"}, f"[{i}/{len(masks)}] {name}")
                print(f"[masks_to_uv] {i}/{len(masks)} {name}")
                gray, w, h = load_mask_grayscale(mp)
                if gray is None or w != h:
                    print(f"  skip (taille invalide {w}x{h})")
                    continue
                uv_arr = reproject_mask(mesh_eval, mw, gray, cam_params, uv_res)
                if props.padding > 0:
                    uv_arr = dilate_uv(uv_arr, iterations=props.padding)
                out_path = os.path.join(out_folder, f"{name}_uv.png")
                save_uv_png(uv_arr, out_path)
                print(f"  -> {out_path}")
        except Exception as e:
            self.report({"ERROR"}, str(e))
            import traceback; traceback.print_exc()
            return {"CANCELLED"}
        finally:
            obj_eval.to_mesh_clear()

        self.report({"INFO"}, f"Termine : {len(masks)} masques reprojets.")
        return {"FINISHED"}


class PBRTK_M2UVProperties(PropertyGroup):
    camera: PointerProperty(
        name="Camera ortho",
        type=bpy.types.Object,
        poll=cam_poll,
    )
    input_folder: StringProperty(
        name="Dossier masques",
        subtype="DIR_PATH",
    )
    output_folder: StringProperty(
        name="Dossier sortie UV",
        subtype="DIR_PATH",
    )
    uv_resolution: EnumProperty(
        name="Resolution UV",
        items=UV_RES_ITEMS,
        default="4096",
    )
    padding: bpy.props.IntProperty(
        name="Padding UV (px)",
        description="Edge padding pour eviter les cracks aux seams UV (0 = desactive)",
        default=4, min=0, max=32,
    )


class PBRTK_PT_M2UVPanel(Panel):
    bl_label       = "PBR Toolkit -- 3. Masks to UV"
    bl_idname      = "PBRTK_PT_m2uv"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "PBR Toolkit"
    bl_order       = 1

    def draw(self, context):
        layout = self.layout
        props  = context.scene.pbrtk_m2uv_props
        layout.label(text="Etape 3 -- Masks to UV :")
        layout.prop(props, "camera")
        if props.camera and "sam_target_mesh" in props.camera:
            layout.label(
                text=f"Mesh : {props.camera['sam_target_mesh']}",
                icon="MESH_DATA",
            )
        layout.prop(props, "input_folder")
        layout.prop(props, "output_folder")
        layout.prop(props, "uv_resolution")
        layout.prop(props, "padding")
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("pbrtk.masks_to_uv", icon="UV_DATA")


classes = (
    PBRTK_M2UVProperties,
    PBRTK_OT_MasksToUV,
    PBRTK_PT_M2UVPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pbrtk_m2uv_props = bpy.props.PointerProperty(
        type=PBRTK_M2UVProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pbrtk_m2uv_props
