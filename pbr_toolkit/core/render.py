"""
render.py — Étape 1 : rendu orthographique top-view via passe DiffCol (Cycles).

Crée/réutilise une caméra ortho PERSISTANTE cadrée sur la bounding box du
mesh, et y écrit le contrat géométrique (camera_contract) que l'étape 3
relira. La passe DiffCol sort l'albédo « à plat » sans ombrage.
"""

import os
import bpy

from . import naming
from . import camera_contract


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


def render_topview(context, settings):
    """Retourne (ok: bool, message: str)."""
    import mathutils

    folder = bpy.path.abspath(settings.project_folder)
    if not folder or not os.path.isdir(folder):
        return False, "Dossier projet invalide."

    obj = context.active_object
    if not obj or obj.type != "MESH":
        return False, "Sélectionner un mesh avant le rendu."

    cam_name = (settings.camera_name or "").strip()
    if not cam_name:
        return False, "Nom de caméra vide."

    base = naming.resolve_base_name(settings, context)
    if not base:
        return False, "Nom de base introuvable."

    resolution = int(settings.render_resolution)
    basename   = naming.topview_stem(base)
    out_path   = os.path.join(folder, naming.topview_filename(base))
    scene      = context.scene
    vl         = scene.view_layers[0]

    # --- Sauvegarde de l'état scène ---
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
    ret      = (False, "Échec inattendu.")

    try:
        (cx, cy), extent, z_max = get_obj_bounds(obj)

        # Caméra du même nom déjà présente : on la remplace (relance), mais on
        # refuse d'écraser un objet homonyme qui ne serait pas une caméra.
        if cam_name in bpy.data.objects:
            old = bpy.data.objects[cam_name]
            if old.type != "CAMERA":
                raise RuntimeError(
                    f"Un objet nommé '{cam_name}' existe déjà et n'est pas une "
                    f"caméra. Renommez-le ou choisissez un autre nom."
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

        # Contrat pour l'étape 3.
        camera_contract.write(cam_obj, camera_contract.CameraContract(
            target_mesh=obj.name, base_name=base,
            center_x=cx, center_y=cy, extent=extent,
            resolution=resolution, z_max=z_max,
        ))

        # --- Cycles + passe DiffCol ---
        scene.render.engine                = "CYCLES"
        scene.render.resolution_x          = resolution
        scene.render.resolution_y          = resolution
        scene.render.resolution_percentage = 100
        scene.render.film_transparent      = False
        if hasattr(scene.cycles, "samples"):
            prev_samples         = scene.cycles.samples
            scene.cycles.samples = 1
        vl.use_pass_diffuse_color = True

        # --- Compositor : RLayers (DiffCol) -> File Output ---
        scene.use_nodes = True
        tree  = scene.node_tree
        nodes = tree.nodes
        links = tree.links

        n_rl = nodes.new("CompositorNodeRLayers")
        n_rl.name  = "__PBRTK_RL__"
        n_rl.scene = scene
        n_rl.layer = vl.name

        n_fo = nodes.new("CompositorNodeOutputFile")
        n_fo.name               = "__PBRTK_FO__"
        n_fo.base_path          = folder
        n_fo.format.file_format = "PNG"
        n_fo.format.color_mode  = "RGB"
        n_fo.format.color_depth = "8"
        n_fo.format.compression = 0
        n_fo.file_slots[0].path = basename

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
            ret = (True, f"Top view → {out_path} (cam: {cam_name})")
        else:
            ret = (False, f"Fichier attendu non trouvé : {out_path}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        # État incohérent : on nettoie la caméra créée.
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
        ret = (False, str(e))

    finally:
        # --- Restauration scène (mais on GARDE la caméra) ---
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
            for n_name in ("__PBRTK_RL__", "__PBRTK_FO__"):
                if n_name in scene.node_tree.nodes:
                    try:
                        scene.node_tree.nodes.remove(scene.node_tree.nodes[n_name])
                    except Exception:
                        pass
        scene.use_nodes = prev_use_nodes

    return ret
