"""
material.py — Étape 4 : node graph PBR ajustable.

Tout le traitement vit dans un node group « PBRToolkit_Controls » (HSV, normal
map, bump, chaînes Roughness/Specular/Subsurface par zone) câblé sur un
Principled BSDF. Le material consomme les masques espace-UV (_uv).
"""

import bpy

from . import image_io


# --- Layout (dans le group) ---
GX_HSV   = -2000
GX_BW    = -1700
GX_NM    = -1700
GX_BUMP  = -1400
GX_CHAIN = -1100
GX_STEP  =   300
GX_IN    = -2400
GX_OUT   =   800

GY_DIFFUSE = 1200
GY_NORMAL  =  600
GY_BUMP    =  400
GY_ROUGH   =  100
GY_SPEC    = -450
GY_SUB     = -950

# --- Layout (material) ---
MX_TEX     = -1400
MX_GRP     =  -400
MX_BSDF    =   400
MX_OUT     =   750
MY_DIFFUSE =  1200
MY_NORMAL  =   600
MY_PLATE   =   200
MY_MASKS   =  -200

GROUP_NAME  = "PBRToolkit_Controls"
GROUP_LABEL = "PBR Toolkit Controls"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nn(nodes, ntype, x, y, label=None):
    n = nodes.new(type=ntype)
    n.location = (x, y)
    if label:
        n.label = label
    return n


def _img_node(nodes, path, cs, x, y, label=None):
    n = _nn(nodes, "ShaderNodeTexImage", x, y, label)
    n.image = image_io.load_datablock(path, cs)
    return n


def _add_socket(grp, socket_type, name, in_out,
                default=None, min_val=None, max_val=None):
    s = grp.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    for attr, val in (("default_value", default),
                      ("min_value", min_val),
                      ("max_value", max_val)):
        if val is not None:
            try:
                setattr(s, attr, val)
            except Exception:
                pass
    return s


# ---------------------------------------------------------------------------
# Node group
# ---------------------------------------------------------------------------

def _build_node_group(tex, n_masks, has_subsurface):
    if GROUP_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GROUP_NAME])

    grp    = bpy.data.node_groups.new(name=GROUP_NAME, type="ShaderNodeTree")
    gnodes = grp.nodes
    glinks = grp.links

    n_gin  = gnodes.new("NodeGroupInput")
    n_gout = gnodes.new("NodeGroupOutput")
    n_gin.location  = (GX_IN,  0)
    n_gout.location = (GX_OUT, 0)

    # --- INPUTS : textures ---
    _add_socket(grp, "NodeSocketColor", "Diffuse",    "INPUT", default=(0.8, 0.8, 0.8, 1.0))
    _add_socket(grp, "NodeSocketColor", "Normal Tex", "INPUT", default=(0.5, 0.5, 1.0, 1.0))
    if tex["mask_plate"]:
        _add_socket(grp, "NodeSocketColor", "Plate Mask", "INPUT", default=(0.0, 0.0, 0.0, 1.0))
    for i in range(1, n_masks + 1):
        _add_socket(grp, "NodeSocketColor", f"Mask {i}", "INPUT", default=(0.0, 0.0, 0.0, 1.0))
    if has_subsurface:
        _add_socket(grp, "NodeSocketColor", "Subsurface Tex", "INPUT", default=(0.8, 0.6, 0.5, 1.0))

    # --- INPUTS : sliders fixes ---
    _add_socket(grp, "NodeSocketFloat", "Hue",             "INPUT", default=0.5,  min_val=0.0, max_val=1.0)
    _add_socket(grp, "NodeSocketFloat", "Saturation",      "INPUT", default=1.0,  min_val=0.0, max_val=2.0)
    _add_socket(grp, "NodeSocketFloat", "Value",           "INPUT", default=1.0,  min_val=0.0, max_val=2.0)
    _add_socket(grp, "NodeSocketFloat", "Normal Strength", "INPUT", default=1.0,  min_val=0.0, max_val=5.0)
    _add_socket(grp, "NodeSocketFloat", "Bump Strength",   "INPUT", default=0.25, min_val=0.0, max_val=2.0)
    _add_socket(grp, "NodeSocketFloat", "Roughness Base",  "INPUT", default=0.5,  min_val=0.0, max_val=2.0)
    _add_socket(grp, "NodeSocketFloat", "Specular Base",   "INPUT", default=0.5,  min_val=0.0, max_val=2.0)
    if has_subsurface:
        _add_socket(grp, "NodeSocketColor", "Subsurface Base", "INPUT", default=(0.5, 0.5, 0.5, 1.0))

    # --- INPUTS : sliders par zone ---
    for i in range(1, n_masks + 1):
        _add_socket(grp, "NodeSocketFloat", f"Roughness Zone {i}", "INPUT", default=0.5, min_val=0.0, max_val=2.0)
        _add_socket(grp, "NodeSocketFloat", f"Rough Invert {i}",   "INPUT", default=0.0, min_val=0.0, max_val=1.0)
        _add_socket(grp, "NodeSocketFloat", f"Specular Zone {i}",  "INPUT", default=0.5, min_val=0.0, max_val=2.0)
        _add_socket(grp, "NodeSocketFloat", f"Spec Invert {i}",    "INPUT", default=0.0, min_val=0.0, max_val=1.0)
        if has_subsurface:
            _add_socket(grp, "NodeSocketColor", f"Subsurface Col {i}", "INPUT", default=(0.8, 0.6, 0.5, 1.0))

    # --- OUTPUTS ---
    _add_socket(grp, "NodeSocketColor",  "Base Color", "OUTPUT")
    _add_socket(grp, "NodeSocketVector", "Normal",     "OUTPUT")
    _add_socket(grp, "NodeSocketFloat",  "Roughness",  "OUTPUT")
    _add_socket(grp, "NodeSocketFloat",  "Specular",   "OUTPUT")
    if tex["mask_plate"]:
        _add_socket(grp, "NodeSocketFloat", "Coat Weight", "OUTPUT")
    if has_subsurface:
        _add_socket(grp, "NodeSocketFloat", "Subsurface Weight", "OUTPUT")

    # --- Nodes internes ---
    n_hsv = _nn(gnodes, "ShaderNodeHueSaturation", GX_HSV, GY_DIFFUSE, "HSV")
    glinks.new(n_gin.outputs["Diffuse"],    n_hsv.inputs["Color"])
    glinks.new(n_gin.outputs["Hue"],        n_hsv.inputs["Hue"])
    glinks.new(n_gin.outputs["Saturation"], n_hsv.inputs["Saturation"])
    glinks.new(n_gin.outputs["Value"],      n_hsv.inputs["Value"])

    n_bw = _nn(gnodes, "ShaderNodeRGBToBW", GX_BW, GY_DIFFUSE - 200, "BW Diffuse")
    glinks.new(n_hsv.outputs["Color"], n_bw.inputs["Color"])

    n_nm = _nn(gnodes, "ShaderNodeNormalMap", GX_NM, GY_NORMAL, "Normal Map")
    n_nm.space = "TANGENT"
    glinks.new(n_gin.outputs["Normal Tex"],      n_nm.inputs["Color"])
    glinks.new(n_gin.outputs["Normal Strength"], n_nm.inputs["Strength"])

    n_bump = _nn(gnodes, "ShaderNodeBump", GX_BUMP, GY_BUMP, "Bump")
    n_bump.inputs["Distance"].default_value = 0.001
    glinks.new(n_bw.outputs["Val"],            n_bump.inputs["Height"])
    glinks.new(n_nm.outputs["Normal"],         n_bump.inputs["Normal"])
    glinks.new(n_gin.outputs["Bump Strength"], n_bump.inputs["Strength"])

    mask_socket_names = [f"Mask {i}" for i in range(1, n_masks + 1)]

    rough_socket = _build_float_chain(gnodes, glinks, n_gin, n_bw,
                                      mask_socket_names, GX_CHAIN, GY_ROUGH, "Roughness")
    spec_socket  = _build_float_chain(gnodes, glinks, n_gin, n_bw,
                                      mask_socket_names, GX_CHAIN, GY_SPEC, "Specular")
    sub_socket = None
    if has_subsurface:
        sub_socket = _build_color_chain(gnodes, glinks, n_gin,
                                       mask_socket_names, GX_CHAIN, GY_SUB)

    # --- Wiring vers Group Output ---
    glinks.new(n_hsv.outputs["Color"],   n_gout.inputs["Base Color"])
    glinks.new(n_bump.outputs["Normal"], n_gout.inputs["Normal"])
    glinks.new(rough_socket,             n_gout.inputs["Roughness"])
    glinks.new(spec_socket,              n_gout.inputs["Specular"])

    if tex["mask_plate"]:
        glinks.new(n_gin.outputs["Plate Mask"], n_gout.inputs["Coat Weight"])

    if has_subsurface and sub_socket:
        n_sub_bw = _nn(gnodes, "ShaderNodeRGBToBW", GX_OUT - 300, GY_SUB, "BW Subsurface")
        glinks.new(sub_socket,              n_sub_bw.inputs["Color"])
        glinks.new(n_sub_bw.outputs["Val"], n_gout.inputs["Subsurface Weight"])

    return grp


def _build_float_chain(gnodes, glinks, n_gin, n_bw,
                       mask_socket_names, x_start, y_base, chain_name):
    """Chaîne Roughness ou Specular (valeurs flottantes par zone)."""
    short    = "Rough" if chain_name == "Roughness" else "Spec"
    base_key = f"{chain_name} Base"

    n_base_mul = _nn(gnodes, "ShaderNodeMath", x_start - 300, y_base,
                     f"BW x {chain_name} Base")
    n_base_mul.operation = "MULTIPLY"
    n_base_mul.use_clamp = True
    glinks.new(n_bw.outputs["Val"],     n_base_mul.inputs[0])
    glinks.new(n_gin.outputs[base_key], n_base_mul.inputs[1])

    n_base_inv = _nn(gnodes, "ShaderNodeInvert", x_start - 300, y_base - 120,
                     f"Invert {chain_name} Base")
    n_base_inv.inputs["Fac"].default_value = 0.0
    glinks.new(n_base_mul.outputs["Value"], n_base_inv.inputs["Color"])

    prev_socket = n_base_inv.outputs["Color"]

    for i, mask_sock_name in enumerate(mask_socket_names):
        zone_idx   = i + 1
        x          = x_start + i * GX_STEP
        zone_key   = f"{chain_name} Zone {zone_idx}"
        invert_key = f"{short} Invert {zone_idx}"

        n_mul = _nn(gnodes, "ShaderNodeMath", x, y_base, f"BW x {chain_name} {zone_idx}")
        n_mul.operation = "MULTIPLY"
        n_mul.use_clamp = True
        glinks.new(n_bw.outputs["Val"],     n_mul.inputs[0])
        glinks.new(n_gin.outputs[zone_key], n_mul.inputs[1])

        n_inv = _nn(gnodes, "ShaderNodeInvert", x, y_base - 130,
                    f"Invert {chain_name} {zone_idx}")
        glinks.new(n_gin.outputs[invert_key], n_inv.inputs["Fac"])
        glinks.new(n_mul.outputs["Value"],    n_inv.inputs["Color"])

        n_mix = _nn(gnodes, "ShaderNodeMix", x, y_base - 280, f"{chain_name} Mix {zone_idx}")
        n_mix.data_type    = "FLOAT"
        n_mix.blend_type   = "MIX"
        n_mix.clamp_factor = True
        glinks.new(n_gin.outputs[mask_sock_name], n_mix.inputs["Factor"])

        # ShaderNodeMix (4.x) expose plusieurs paires A/B (une par data_type) :
        # on cible les sockets FLOAT (type VALUE).
        float_socks = [s for s in n_mix.inputs if s.name in ("A", "B") and s.type == "VALUE"]
        if len(float_socks) >= 2:
            glinks.new(prev_socket,            float_socks[0])
            glinks.new(n_inv.outputs["Color"], float_socks[1])
        else:
            glinks.new(prev_socket,            n_mix.inputs[2])
            glinks.new(n_inv.outputs["Color"], n_mix.inputs[3])

        float_outs = [s for s in n_mix.outputs if s.type == "VALUE"]
        prev_socket = float_outs[0] if float_outs else n_mix.outputs[-1]

    return prev_socket


def _build_color_chain(gnodes, glinks, n_gin, mask_socket_names, x_start, y_base):
    """Chaîne Subsurface (couleur par zone)."""
    prev_socket = n_gin.outputs["Subsurface Base"]
    for i, mask_sock_name in enumerate(mask_socket_names):
        zone_idx = i + 1
        x        = x_start + i * GX_STEP
        col_key  = f"Subsurface Col {zone_idx}"

        n_mix = _nn(gnodes, "ShaderNodeMix", x, y_base, f"SUBSURFACE Mix {zone_idx}")
        n_mix.data_type    = "RGBA"
        n_mix.blend_type   = "MIX"
        n_mix.clamp_factor = True
        glinks.new(n_gin.outputs[mask_sock_name], n_mix.inputs["Factor"])
        glinks.new(prev_socket,                   n_mix.inputs["A"])
        glinks.new(n_gin.outputs[col_key],        n_mix.inputs["B"])
        prev_socket = n_mix.outputs["Result"]
    return prev_socket


# ---------------------------------------------------------------------------
# Material builder
# ---------------------------------------------------------------------------

def build_material(obj, tex, base):
    """
    Construit le material à partir d'un dict `tex` déjà résolu (convention +
    overrides). Retourne (ok: bool, message: str).
    """
    n_masks        = len(tex["masks"])
    has_subsurface = tex["subsurface"] is not None

    if not tex["diffuse"]:
        return False, f"Aucun fichier _diffuse trouvé pour '{base}'."
    if not tex["normal"]:
        return False, f"Aucun fichier _normal trouvé pour '{base}'."

    grp = _build_node_group(tex, n_masks, has_subsurface)

    mat_name = base or "PBRToolkit_Material"
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name])
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # 1. Image Texture nodes (espace-UV)
    n_diff = _img_node(nodes, tex["diffuse"], "sRGB",      MX_TEX, MY_DIFFUSE, "Diffuse")
    n_norm = _img_node(nodes, tex["normal"],  "Non-Color", MX_TEX, MY_NORMAL,  "Normal Tex")

    n_plate = None
    if tex["mask_plate"]:
        n_plate = _img_node(nodes, tex["mask_plate"], "Non-Color", MX_TEX, MY_PLATE, "Mask Plate")

    mask_img_nodes = []
    for i, (path, inv, idx) in enumerate(tex["masks"]):
        y = MY_MASKS - i * 220
        n_tex = _img_node(nodes, path, "Non-Color", MX_TEX, y, f"Mask_{idx}")
        if inv:
            n_pre_inv = _nn(nodes, "ShaderNodeInvert", MX_TEX + 350, y, f"Pre-Invert Mask_{idx}")
            n_pre_inv.inputs["Fac"].default_value = 1.0
            links.new(n_tex.outputs["Color"], n_pre_inv.inputs["Color"])
            mask_img_nodes.append(n_pre_inv)
        else:
            mask_img_nodes.append(n_tex)

    n_sub_tex = None
    if has_subsurface:
        y = MY_MASKS - n_masks * 220 - 220
        n_sub_tex = _img_node(nodes, tex["subsurface"], "sRGB", MX_TEX, y, "Subsurface Tex")

    # 2. Group node
    n_grp = _nn(nodes, "ShaderNodeGroup", MX_GRP, 0, GROUP_LABEL)
    n_grp.node_tree = grp
    n_grp.width     = 280

    links.new(n_diff.outputs["Color"], n_grp.inputs["Diffuse"])
    links.new(n_norm.outputs["Color"], n_grp.inputs["Normal Tex"])
    if n_plate:
        links.new(n_plate.outputs["Color"], n_grp.inputs["Plate Mask"])
    for i, n_mask in enumerate(mask_img_nodes):
        links.new(n_mask.outputs["Color"], n_grp.inputs[f"Mask {i + 1}"])
    if n_sub_tex:
        links.new(n_sub_tex.outputs["Color"], n_grp.inputs["Subsurface Tex"])

    # 3. Principled BSDF
    n_bsdf = _nn(nodes, "ShaderNodeBsdfPrincipled", MX_BSDF, 300, "Principled BSDF")
    n_bsdf.inputs["Metallic"].default_value = 0.0
    n_bsdf.inputs["IOR"].default_value      = 1.5
    if "Alpha" in n_bsdf.inputs:
        n_bsdf.inputs["Alpha"].default_value = 1.0

    links.new(n_grp.outputs["Base Color"], n_bsdf.inputs["Base Color"])
    links.new(n_grp.outputs["Normal"],     n_bsdf.inputs["Normal"])
    links.new(n_grp.outputs["Roughness"],  n_bsdf.inputs["Roughness"])

    spec_input = (n_bsdf.inputs.get("Specular IOR Level")
                  or n_bsdf.inputs.get("IOR Level")
                  or n_bsdf.inputs.get("Specular"))
    if spec_input:
        links.new(n_grp.outputs["Specular"], spec_input)

    if tex["mask_plate"]:
        coat_input = (n_bsdf.inputs.get("Coat Weight")
                      or n_bsdf.inputs.get("Clearcoat"))
        if coat_input:
            links.new(n_grp.outputs["Coat Weight"], coat_input)

    if has_subsurface:
        sub_w = (n_bsdf.inputs.get("Subsurface Weight")
                 or n_bsdf.inputs.get("Weight"))
        if sub_w:
            links.new(n_grp.outputs["Subsurface Weight"], sub_w)

    # 4. Material Output
    n_out = _nn(nodes, "ShaderNodeOutputMaterial", MX_OUT, 300, "Material Output")
    links.new(n_bsdf.outputs["BSDF"], n_out.inputs["Surface"])

    return True, f"Material '{mat_name}' créé ({n_masks} zone(s))."
