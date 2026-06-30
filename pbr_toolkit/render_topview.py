"""
render_topview.py
=================
Etape 1 -- Rendu orthographique top-view via passe DiffCol (Cycles).

La camera ortho est PERSISTANTE (non supprimee apres rendu) et son nom est
configurable. Elle sert de contrat avec l'etape masks_to_uv pour la
reprojection (custom props sam_*).
"""

import bpy
import os
from bpy.props import StringProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup


RESOLUTION_ITEMS = [
    ("1024", "1K -- 1024px", ""),
    ("2048", "2K -- 2048px (recommande SAM)", ""),
    ("4096", "4K -- 4096px", ""),
]


def get_obj_bounds(obj):
    import mathutils
    ws = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [v.x for v in ws]
    ys = [v.y for v in ws]
    zs = [v.z for v in ws]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    extent = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.08
    return (cx, cy), extent, max(zs)


class PBRTK_OT_RenderTopView(Operator):
    bl_idname      = "pbrtk.render_topview"
    bl_label       = "Render Top View"
    bl_description = "Rendu orthographique top-view (passe DiffCol) pour SAM"
    bl_options     = {"REGISTER"}

    def execute(self, context):
        import mathutils

        props  = context.scene.pbrtk_topview_props
        folder = bpy.path.abspath(props.output_folder)

        if not folder or not os.path.isdir(folder):
            self.report({"ERROR"}, "Dossier de sortie invalide.")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Selectionner un mesh avant le rendu.")
            return {"CANCELLED"}

        cam_name = props.camera_name.strip()
        if not cam_name:
            self.report({"ERROR"}, "Nom de camera vide.")
            return {"CANCELLED"}

        resolution = int(props.render_resolution)
        basename   = f"{obj.name}_topview"
        out_path   = os.path.join(folder, f"{basename}.png")
        scene      = context.scene
        vl         = scene.view_layers[0]

        # --- Sauvegarder ---
        prev_engine      = scene.render.engine
        prev_res_x       = scene.render.resolution_x
        prev_res_y       = scene.render.resolution_y
        prev_res_pct     = scene.render.resolution_percentage
        prev_filepath    = scene.render.filepath
        prev_file_format = scene.render.image_settings.file_format
        prev_color_mode  = scene.render.image_settings.color_mode
        prev_transparent = scene.render.film_transparent
        prev_cam         = scene.camera
        prev_samples     = None
        prev_use_nodes   = scene.use_nodes
        prev_diffcol     = vl.use_pass_diffuse_color

        cam_obj  = None
        cam_data = None

        try:
            # --- Camera ortho top (PERSISTANTE) ---
            (cx, cy), extent, z_max = get_obj_bounds(obj)

            # Si une camera du meme nom existe deja, on la supprime pour
            # repartir propre (l'utilisateur a relance le rendu). On refuse en
            # revanche d'ecraser un objet homonyme qui ne serait pas une camera.
            if cam_name in bpy.data.objects:
                old = bpy.data.objects[cam_name]
                if old.type != "CAMERA":
                    raise RuntimeError(
                        f"Un objet nomme '{cam_name}' existe deja et n'est pas "
                        f"une camera. Renommez-le ou choisissez un autre nom."
                    )
                old_data = old.data
                bpy.data.objects.remove(old, do_unlink=True)
                if old_data and old_data.users == 0:
                    bpy.data.cameras.remove(old_data)

            cam_data = bpy.data.cameras.new(name=cam_name)
            cam_data.type        = "ORTHO"
            cam_data.ortho_scale = extent
            cam_data.clip_start  = 0.001
            cam_data.clip_end    = 9999.0
            cam_obj = bpy.data.objects.new(name=cam_name, object_data=cam_data)
            scene.collection.objects.link(cam_obj)
            cam_obj.location       = mathutils.Vector((cx, cy, z_max + extent))
            cam_obj.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), "XYZ")
            scene.camera           = cam_obj

            # Custom properties = contrat pour masks_to_uv
            cam_obj["sam_target_mesh"]   = obj.name
            cam_obj["sam_resolution"]    = resolution
            cam_obj["sam_extent"]        = extent
            cam_obj["sam_center_x"]      = cx
            cam_obj["sam_center_y"]      = cy
            cam_obj["sam_z_max"]         = z_max

            # --- Cycles + passe DiffCol ---
            scene.render.engine              = "CYCLES"
            scene.render.resolution_x        = resolution
            scene.render.resolution_y        = resolution
            scene.render.resolution_percentage = 100
            scene.render.film_transparent    = False
            if hasattr(scene.cycles, "samples"):
                prev_samples         = scene.cycles.samples
                scene.cycles.samples = 1
            vl.use_pass_diffuse_color = True

            # --- Compositor ---
            scene.use_nodes = True
            tree  = scene.node_tree
            nodes = tree.nodes
            links = tree.links

            n_rl = nodes.new("CompositorNodeRLayers")
            n_rl.name  = "__SAM_RL__"
            n_rl.scene = scene
            n_rl.layer = vl.name

            n_fo = nodes.new("CompositorNodeOutputFile")
            n_fo.name                      = "__SAM_FO__"
            n_fo.base_path                 = folder
            n_fo.format.file_format        = "PNG"
            n_fo.format.color_mode         = "RGB"
            n_fo.format.color_depth        = "8"
            n_fo.format.compression        = 0
            n_fo.file_slots[0].path        = basename

            diffcol_sock = None
            for sock in n_rl.outputs:
                if sock.name in ("DiffCol", "Diffuse Color", "DIFFUSE_COLOR"):
                    diffcol_sock = sock
                    break
                if "diff" in sock.name.lower() and "col" in sock.name.lower():
                    diffcol_sock = sock
                    break

            if diffcol_sock is None:
                avail = [s.name for s in n_rl.outputs]
                raise RuntimeError(f"Passe DiffCol introuvable. Passes dispo : {avail}")

            links.new(diffcol_sock, n_fo.inputs[0])

            # --- Rendu ---
            bpy.ops.render.render(write_still=False)

            frame_str = f"{scene.frame_current:04d}"
            framed    = os.path.join(folder, f"{basename}{frame_str}.png")
            if os.path.exists(framed) and not os.path.exists(out_path):
                os.rename(framed, out_path)
            elif os.path.exists(framed):
                os.replace(framed, out_path)

            if os.path.exists(out_path):
                self.report({"INFO"}, f"Top view -> {out_path} (cam: {cam_name})")
            else:
                self.report({"WARNING"}, f"Fichier attendu non trouve : {out_path}")

            result = {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, str(e))
            import traceback; traceback.print_exc()
            # En cas d'erreur, on nettoie la camera (etat incoherent)
            if cam_obj:
                try:
                    bpy.data.objects.remove(cam_obj, do_unlink=True)
                except Exception:
                    pass
            if cam_data and cam_name in bpy.data.cameras:
                try:
                    bpy.data.cameras.remove(bpy.data.cameras[cam_name])
                except Exception:
                    pass
            result = {"CANCELLED"}

        finally:
            # --- Restaurer scene (mais pas la camera : on la garde) ---
            scene.render.engine                     = prev_engine
            scene.render.resolution_x               = prev_res_x
            scene.render.resolution_y               = prev_res_y
            scene.render.resolution_percentage      = prev_res_pct
            scene.render.filepath                   = prev_filepath
            scene.render.image_settings.file_format = prev_file_format
            scene.render.image_settings.color_mode  = prev_color_mode
            scene.render.film_transparent           = prev_transparent
            scene.camera                            = prev_cam
            vl.use_pass_diffuse_color               = prev_diffcol
            if prev_samples is not None:
                scene.cycles.samples = prev_samples

            if scene.use_nodes and scene.node_tree:
                for n_name in ["__SAM_RL__", "__SAM_FO__"]:
                    if n_name in scene.node_tree.nodes:
                        try:
                            scene.node_tree.nodes.remove(scene.node_tree.nodes[n_name])
                        except Exception:
                            pass
            scene.use_nodes = prev_use_nodes

        return result


class PBRTK_TopViewProperties(PropertyGroup):
    output_folder: StringProperty(
        name="Dossier de sortie",
        default="",
        subtype="DIR_PATH",
    )
    render_resolution: EnumProperty(
        name="Resolution",
        items=RESOLUTION_ITEMS,
        default="2048",
    )
    camera_name: StringProperty(
        name="Nom camera",
        description="Nom de la camera ortho persistante (reutilisee par masks_to_uv)",
        default="SAM_TopView_Cam",
    )


class PBRTK_PT_TopViewPanel(Panel):
    bl_label       = "PBR Toolkit -- 1. Render Top View"
    bl_idname      = "PBRTK_PT_topview"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "PBR Toolkit"
    bl_order       = 0

    def draw(self, context):
        layout = self.layout
        props  = context.scene.pbrtk_topview_props

        layout.label(text="Etape 1 -- Render Top View :")
        layout.prop(props, "output_folder", text="Dossier sortie")
        layout.prop(props, "render_resolution")
        layout.prop(props, "camera_name")

        obj = context.active_object
        if obj and obj.type == "MESH":
            layout.label(text=f"Mesh : {obj.name}", icon="MESH_DATA")
            layout.label(text=f"Sortie : {obj.name}_topview.png", icon="INFO")
        else:
            layout.label(text="Selectionner un mesh", icon="ERROR")

        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("pbrtk.render_topview", icon="RENDER_STILL")

        layout.separator()
        layout.label(text="Etape 2 -- Lancer sam_segment.py", icon="INFO")
        layout.label(text="Etape 3 -- masks_to_uv (meme camera)", icon="INFO")


classes = (
    PBRTK_TopViewProperties,
    PBRTK_OT_RenderTopView,
    PBRTK_PT_TopViewPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pbrtk_topview_props = bpy.props.PointerProperty(
        type=PBRTK_TopViewProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pbrtk_topview_props
