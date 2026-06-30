"""
reproject.py — Étape 3 : reprojection des masques espace-image vers l'espace UV.

Reprojection inverse vectorisée (NumPy) : pour chaque triangle du mesh ÉVALUÉ
(modifiers appliqués, cohérent avec le rendu), on rasterise dans l'espace UV ;
pour chaque texel on calcule sa position world via barycentriques puis on
projette sur l'image source via le contrat caméra ortho. Pas de raycasting,
pas de trous.
"""

import os
import bpy
import numpy as np

from . import naming
from . import camera_contract
from . import image_io


def reproject_mask(mesh, mw, mask_img, contract, uv_res):
    """
    Reprojette un masque espace-image vers une texture UV.
    `mesh` est déjà triangulé (calc_loop_triangles) ; `mw` sa matrice world.
    Retourne un array (uv_res, uv_res) float32 dans [0, 1].
    """
    cx      = contract.center_x
    cy      = contract.center_y
    extent  = contract.extent
    src_res = mask_img.shape[0]  # masque carré

    out = np.zeros((uv_res, uv_res), dtype=np.float32)
    uv_layer = mesh.uv_layers.active.data

    for tri in mesh.loop_triangles:
        v0 = mw @ mesh.vertices[tri.vertices[0]].co
        v1 = mw @ mesh.vertices[tri.vertices[1]].co
        v2 = mw @ mesh.vertices[tri.vertices[2]].co
        uv0 = uv_layer[tri.loops[0]].uv
        uv1 = uv_layer[tri.loops[1]].uv
        uv2 = uv_layer[tri.loops[2]].uv

        # UV en pixels (origine bas-gauche conservée, flip Y à la fin)
        u0p, v0p = uv0.x * uv_res, uv0.y * uv_res
        u1p, v1p = uv1.x * uv_res, uv1.y * uv_res
        u2p, v2p = uv2.x * uv_res, uv2.y * uv_res

        u_min = max(int(np.floor(min(u0p, u1p, u2p))), 0)
        u_max = min(int(np.ceil (max(u0p, u1p, u2p))), uv_res - 1)
        v_min = max(int(np.floor(min(v0p, v1p, v2p))), 0)
        v_max = min(int(np.ceil (max(v0p, v1p, v2p))), uv_res - 1)
        if u_max < u_min or v_max < v_min:
            continue

        us, vs = np.meshgrid(
            np.arange(u_min, u_max + 1) + 0.5,
            np.arange(v_min, v_max + 1) + 0.5,
            indexing="xy",
        )

        denom = (v1p - v2p) * (u0p - u2p) + (u2p - u1p) * (v0p - v2p)
        if abs(denom) < 1e-12:
            continue
        b0 = ((v1p - v2p) * (us - u2p) + (u2p - u1p) * (vs - v2p)) / denom
        b1 = ((v2p - v0p) * (us - u2p) + (u0p - u2p) * (vs - v2p)) / denom
        b2 = 1.0 - b0 - b1

        inside = (b0 >= 0) & (b1 >= 0) & (b2 >= 0)
        if not np.any(inside):
            continue

        wx = b0 * v0.x + b1 * v1.x + b2 * v2.x
        wy = b0 * v0.y + b1 * v1.y + b2 * v2.y

        px = ((wx - cx) / extent + 0.5) * src_res
        py = ((cy - wy) / extent + 0.5) * src_res  # Y inversé (image top-down)
        ix = np.clip(px.astype(np.int32), 0, src_res - 1)
        iy = np.clip(py.astype(np.int32), 0, src_res - 1)

        vals = mask_img[iy, ix]

        out_y = uv_res - 1 - (v_min + np.arange(vs.shape[0]))
        out_y_grid = np.repeat(out_y[:, None], us.shape[1], axis=1)
        out_x_grid = np.repeat((u_min + np.arange(us.shape[1]))[None, :],
                               vs.shape[0], axis=0)

        sel_y = out_y_grid[inside]
        sel_x = out_x_grid[inside]
        out[sel_y, sel_x] = np.maximum(out[sel_y, sel_x], vals[inside])

    return out


def dilate_uv(arr, iterations=4):
    """Edge padding : étend les valeurs non-nulles sur les texels voisins vides."""
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


def reproject_all(context, settings):
    """Retourne (ok: bool, message: str)."""
    folder = bpy.path.abspath(settings.project_folder)
    if not folder or not os.path.isdir(folder):
        return False, "Dossier projet invalide."

    cam = settings.camera_override or bpy.data.objects.get((settings.camera_name or "").strip())
    if not camera_contract.has_contract(cam):
        return False, ("Caméra de contrat introuvable — lance d'abord "
                       "l'étape 1 (Render Top View).")
    contract = camera_contract.read(cam)

    mesh_obj = bpy.data.objects.get(contract.target_mesh)
    if not mesh_obj or mesh_obj.type != "MESH":
        return False, f"Mesh cible '{contract.target_mesh}' introuvable."

    base   = contract.base_name or naming.resolve_base_name(settings, context)
    masks  = naming.list_source_masks(folder, base)
    if not masks:
        return False, f"Aucun masque espace-image trouvé pour '{base}'."

    uv_res = int(settings.uv_resolution)
    padding = int(settings.uv_padding)

    # Mesh évalué (modifiers appliqués) ; évalué/triangulé une seule fois.
    deps      = context.evaluated_depsgraph_get()
    obj_eval  = mesh_obj.evaluated_get(deps)
    mesh_eval = obj_eval.to_mesh()
    try:
        if not mesh_eval.uv_layers.active:
            return False, "Le mesh n'a pas de UV map active."
        mesh_eval.calc_loop_triangles()
        mw = obj_eval.matrix_world.copy()

        for i, mp in enumerate(masks, 1):
            name = os.path.splitext(os.path.basename(mp))[0]
            print(f"[pbr_toolkit] reproject {i}/{len(masks)} {name}")
            gray, w, h = image_io.load_gray(mp)
            if gray is None or w != h:
                print(f"  skip (taille invalide {w}x{h})")
                continue
            uv_arr = reproject_mask(mesh_eval, mw, gray, contract, uv_res)
            if padding > 0:
                uv_arr = dilate_uv(uv_arr, iterations=padding)
            out_path = naming.uv_output_path(mp, folder)
            image_io.save_gray_png(uv_arr, out_path)
            print(f"  -> {out_path}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)
    finally:
        obj_eval.to_mesh_clear()

    return True, f"Terminé : {len(masks)} masque(s) reprojeté(s)."
