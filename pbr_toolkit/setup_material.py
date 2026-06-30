"""
setup_material.py
=================
Etape 4 -- Construction du node graph PBR pour la photogrammetrie food.
Tout le traitement est INSIDE le node group "PBRToolkit_Controls".

NODE GROUP structure :
  INPUTS  : texture sockets (Diffuse, Normal, Plate Mask, Mask 1..N, Subsurface)
            + control sliders (Hue/Sat/Val, Normal/Bump strength)
            + per-zone controls (Roughness Zone N, Rough Invert N,
                                 Specular Zone N, Spec Invert N,
                                 Subsurface Col N)
  INSIDE  : HSV, BW, NormalMap, Bump, Roughness chain, Specular chain,
            Subsurface chain
  OUTPUTS : Base Color (HSV), Normal (Bump), Roughness, Specular,
            Coat Weight (pass-through), Subsurface Weight

MAIN MATERIAL (outside group) :
  Image Texture nodes -> Group inputs
  Group outputs       -> Principled BSDF

NAMING CONVENTION :
  {dish}_diffuse.png
  {dish}_normal.png
  {dish}_mask_plate.png
  {dish}_mask_1.png  {dish}_mask_2.png ...
  {dish}_mask_1_inv.png  (pre-inverted at load)
  {dish}_subsurface.png  (optional)
"""

import bpy
import os
import re
from bpy.props import StringProperty
from bpy.types import Panel, Operator, PropertyGroup


# ---------------------------------------------------------------------------
# Layout constants (inside group)
# ---------------------------------------------------------------------------

GX_IN       = -2400   # Group Input node
GX_HSV      = -2000
GX_BW       = -1700
GX_NM       = -1700
GX_BUMP     = -1400
GX_CHAIN    = -1100
GX_STEP     =  300
GX_OUT      =  800    # Group Output node

GY_DIFFUSE  =  1200
GY_NORMAL   =   600
GY_BUMP     =   400
GY_ROUGH    =   100
GY_SPEC     =  -450
GY_SUB      =  -950
GY_MASKS    = -1400   # mask sockets in Group Input

# Main material layout
MX_TEX      = -1400
MX_GRP      =  -400
MX_BSDF     =   400
MX_OUT      =   750
MY_DIFFUSE  =  1200
MY_NORMAL   =   600
MY_PLATE    =   200
MY_MASKS    =  -200


# ---------------------------------------------------------------------------
# Texture scanner
# ---------------------------------------------------------------------------

def find_textures(folder):
    result = {
        "diffuse":    None,
        "normal":     None,
        "mask_plate": None,
        "masks":      [],
        "subsurface": None,
    }
    raw = []
    for f in os.listdir(folder):
        path = os.path.join(folder, f)
        fl   = f.lower()
        if re.search(r"_diffuse\.", fl):
            result["diffuse"] = path
        elif re.search(r"_normal\.", fl):
            result["normal"] = path
        elif re.search(r"_subsurface\.", fl):
            result["subsurface"] = path
        elif re.search(r"_mask_plate\.", fl):
            result["mask_plate"] = path
        elif re.search(r"_mask_(\d+)", fl):
            m   = re.search(r"_mask_(\d+)", fl)
            idx = int(m.group(1))
            inv = "_inv." in fl
            raw.append((idx, path, inv))
    raw.sort(key=lambda x: x[0])
    result["masks"] = [(p, inv, idx) for (idx, p, inv) in raw]
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def nn(nodes, ntype, x, y, label=None):
    n = nodes.new(type=ntype)
    n.location = (x, y)
    if label:
        n.label = label
    return n


def load_img(path, colorspace="sRGB"):
    name = os.path.basename(path)
    if name in bpy.data.images:
        return bpy.data.images[name]
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = colorspace
    return img


def img_node(nodes, path, cs, x, y, label=None):
    n = nn(nodes, "ShaderNodeTexImage", x, y, label)
    n.image = load_img(path, cs)
    return n


def add_grp_socket(grp, socket_type, name, in_out,
                   default=None, min_val=None, max_val=None):
    s = grp.interface.new_socket(
        name=name, in_out=in_out, socket_type=socket_type
    )
    if default is not None:
        try:
            s.default_value = default
        except Exception:
            pass
    if min_val is not None:
        try:
            s.min_value = min_val
        except Exception:
            pass
    if max_val is not None:
        try:
            s.max_value = max_val
        except Exception:
            pass
    return s


# ---------------------------------------------------------------------------
# Build node group (everything inside)
# ---------------------------------------------------------------------------

def build_node_group(tex, n_masks, has_subsurface, mask_inv_flags):
    """
    Builds the PBRToolkit_Controls node group.
    All processing nodes are inside the group.
    Returns the group data-block.
    """
    grp_name = "PBRToolkit_Controls"
    if grp_name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[grp_name])

    grp    = bpy.data.node_groups.new(name=grp_name, type="ShaderNodeTree")
    gnodes = grp.nodes
    glinks = grp.links

    # -- Group IO nodes --
    n_gin  = gnodes.new("NodeGroupInput")
    n_gout = gnodes.new("NodeGroupOutput")
    n_gin.location  = (GX_IN,  0)
    n_gout.location = (GX_OUT, 0)

    # ------------------------------------------------------------------
    # GROUP INPUTS
    # ------------------------------------------------------------------

    # Texture sockets (Color type - receive from Image Texture nodes outside)
    add_grp_socket(grp, "NodeSocketColor",  "Diffuse",     "INPUT",
                   default=(0.8, 0.8, 0.8, 1.0))
    add_grp_socket(grp, "NodeSocketColor",  "Normal Tex",  "INPUT",
                   default=(0.5, 0.5, 1.0, 1.0))
    if tex["mask_plate"]:
        add_grp_socket(grp, "NodeSocketColor", "Plate Mask", "INPUT",
                       default=(0.0, 0.0, 0.0, 1.0))
    for i in range(1, n_masks + 1):
        add_grp_socket(grp, "NodeSocketColor", "Mask {}".format(i), "INPUT",
                       default=(0.0, 0.0, 0.0, 1.0))
    if has_subsurface:
        add_grp_socket(grp, "NodeSocketColor", "Subsurface Tex", "INPUT",
                       default=(0.8, 0.6, 0.5, 1.0))

    # Control sliders - fixed
    add_grp_socket(grp, "NodeSocketFloat", "Hue",            "INPUT",
                   default=0.5,  min_val=0.0, max_val=1.0)
    add_grp_socket(grp, "NodeSocketFloat", "Saturation",     "INPUT",
                   default=1.0,  min_val=0.0, max_val=2.0)
    add_grp_socket(grp, "NodeSocketFloat", "Value",          "INPUT",
                   default=1.0,  min_val=0.0, max_val=2.0)
    add_grp_socket(grp, "NodeSocketFloat", "Normal Strength","INPUT",
                   default=1.0,  min_val=0.0, max_val=5.0)
    add_grp_socket(grp, "NodeSocketFloat", "Bump Strength",  "INPUT",
                   default=0.25, min_val=0.0, max_val=2.0)
    add_grp_socket(grp, "NodeSocketFloat", "Roughness Base", "INPUT",
                   default=0.5,  min_val=0.0, max_val=2.0)
    add_grp_socket(grp, "NodeSocketFloat", "Specular Base",  "INPUT",
                   default=0.5,  min_val=0.0, max_val=2.0)
    if has_subsurface:
        add_grp_socket(grp, "NodeSocketColor", "Subsurface Base", "INPUT",
                       default=(0.5, 0.5, 0.5, 1.0))

    # Control sliders - per zone
    for i in range(1, n_masks + 1):
        add_grp_socket(grp, "NodeSocketFloat",
                       "Roughness Zone {}".format(i), "INPUT",
                       default=0.5, min_val=0.0, max_val=2.0)
        add_grp_socket(grp, "NodeSocketFloat",
                       "Rough Invert {}".format(i), "INPUT",
                       default=0.0, min_val=0.0, max_val=1.0)
        add_grp_socket(grp, "NodeSocketFloat",
                       "Specular Zone {}".format(i), "INPUT",
                       default=0.5, min_val=0.0, max_val=2.0)
        add_grp_socket(grp, "NodeSocketFloat",
                       "Spec Invert {}".format(i), "INPUT",
                       default=0.0, min_val=0.0, max_val=1.0)
        if has_subsurface:
            add_grp_socket(grp, "NodeSocketColor",
                           "Subsurface Col {}".format(i), "INPUT",
                           default=(0.8, 0.6, 0.5, 1.0))

    # ------------------------------------------------------------------
    # GROUP OUTPUTS
    # ------------------------------------------------------------------
    add_grp_socket(grp, "NodeSocketColor",  "Base Color",       "OUTPUT")
    add_grp_socket(grp, "NodeSocketVector", "Normal",           "OUTPUT")
    add_grp_socket(grp, "NodeSocketFloat",  "Roughness",        "OUTPUT")
    add_grp_socket(grp, "NodeSocketFloat",  "Specular",         "OUTPUT")
    if tex["mask_plate"]:
        add_grp_socket(grp, "NodeSocketFloat", "Coat Weight",   "OUTPUT")
    if has_subsurface:
        add_grp_socket(grp, "NodeSocketFloat", "Subsurface Weight", "OUTPUT")

    # ------------------------------------------------------------------
    # NODES INSIDE THE GROUP
    # ------------------------------------------------------------------

    # 1. HSV on diffuse
    n_hsv = nn(gnodes, "ShaderNodeHueSaturation", GX_HSV, GY_DIFFUSE, "HSV")
    glinks.new(n_gin.outputs["Diffuse"],      n_hsv.inputs["Color"])
    glinks.new(n_gin.outputs["Hue"],          n_hsv.inputs["Hue"])
    glinks.new(n_gin.outputs["Saturation"],   n_hsv.inputs["Saturation"])
    glinks.new(n_gin.outputs["Value"],        n_hsv.inputs["Value"])

    # 2. RGB to BW (from HSV output)
    n_bw = nn(gnodes, "ShaderNodeRGBToBW", GX_BW, GY_DIFFUSE - 200, "BW Diffuse")
    glinks.new(n_hsv.outputs["Color"], n_bw.inputs["Color"])

    # 3. Normal Map
    n_nm = nn(gnodes, "ShaderNodeNormalMap", GX_NM, GY_NORMAL, "Normal Map")
    n_nm.space = "TANGENT"
    glinks.new(n_gin.outputs["Normal Tex"],       n_nm.inputs["Color"])
    glinks.new(n_gin.outputs["Normal Strength"],  n_nm.inputs["Strength"])

    # 4. Bump
    n_bump = nn(gnodes, "ShaderNodeBump", GX_BUMP, GY_BUMP, "Bump")
    n_bump.inputs["Distance"].default_value = 0.001
    glinks.new(n_bw.outputs["Val"],               n_bump.inputs["Height"])
    glinks.new(n_nm.outputs["Normal"],            n_bump.inputs["Normal"])
    glinks.new(n_gin.outputs["Bump Strength"],    n_bump.inputs["Strength"])

    # 5. Mask nodes list (inside group, referencing Group Input sockets)
    #    Each "mask" is represented by its Group Input socket name
    mask_socket_names = ["Mask {}".format(i) for i in range(1, n_masks + 1)]

    # 6. Roughness chain
    rough_socket = _build_float_chain_inside(
        gnodes, glinks, n_gin, n_bw,
        mask_socket_names,
        GX_CHAIN, GY_ROUGH, "Roughness"
    )

    # 7. Specular chain
    spec_socket = _build_float_chain_inside(
        gnodes, glinks, n_gin, n_bw,
        mask_socket_names,
        GX_CHAIN, GY_SPEC, "Specular"
    )

    # 8. Subsurface chain
    sub_socket = None
    if has_subsurface:
        sub_socket = _build_color_chain_inside(
            gnodes, glinks, n_gin,
            mask_socket_names,
            GX_CHAIN, GY_SUB
        )

    # ------------------------------------------------------------------
    # Wire to Group Output
    # ------------------------------------------------------------------
    glinks.new(n_hsv.outputs["Color"],   n_gout.inputs["Base Color"])
    glinks.new(n_bump.outputs["Normal"], n_gout.inputs["Normal"])
    glinks.new(rough_socket,             n_gout.inputs["Roughness"])
    glinks.new(spec_socket,              n_gout.inputs["Specular"])

    if tex["mask_plate"]:
        glinks.new(n_gin.outputs["Plate Mask"], n_gout.inputs["Coat Weight"])

    if has_subsurface and sub_socket:
        # Subsurface Weight needs a float, so convert color to BW
        n_sub_bw = nn(gnodes, "ShaderNodeRGBToBW",
                      GX_OUT - 300, GY_SUB, "BW Subsurface")
        glinks.new(sub_socket,               n_sub_bw.inputs["Color"])
        glinks.new(n_sub_bw.outputs["Val"],  n_gout.inputs["Subsurface Weight"])

    return grp


# ---------------------------------------------------------------------------
# Chain builders (inside group)
# ---------------------------------------------------------------------------

def _build_float_chain_inside(gnodes, glinks, n_gin, n_bw,
                               mask_socket_names, x_start, y_base, chain_name):
    """
    Roughness or Specular chain inside the group.
    Uses n_gin.outputs[socket_name] for mask factors and control values.
    """
    short = "Rough" if chain_name == "Roughness" else "Spec"

    # Base (no mask) - value from group input
    base_key = "{} Base".format(chain_name)

    n_base_mul = nn(gnodes, "ShaderNodeMath",
                    x_start - 300, y_base,
                    "BW x {} Base".format(chain_name))
    n_base_mul.operation = "MULTIPLY"
    n_base_mul.use_clamp = True
    glinks.new(n_bw.outputs["Val"],           n_base_mul.inputs[0])
    glinks.new(n_gin.outputs[base_key],       n_base_mul.inputs[1])

    n_base_inv = nn(gnodes, "ShaderNodeInvert",
                    x_start - 300, y_base - 120,
                    "Invert {} Base".format(chain_name))
    n_base_inv.inputs["Fac"].default_value = 0.0
    glinks.new(n_base_mul.outputs["Value"], n_base_inv.inputs["Color"])

    prev_socket = n_base_inv.outputs["Color"]

    for i, mask_sock_name in enumerate(mask_socket_names):
        zone_idx   = i + 1
        x          = x_start + i * GX_STEP
        y          = y_base
        zone_key   = "{} Zone {}".format(chain_name, zone_idx)
        invert_key = "{} Invert {}".format(short, zone_idx)

        # BW * Zone value (from group input)
        n_mul = nn(gnodes, "ShaderNodeMath", x, y,
                   "BW x {} {}".format(chain_name, zone_idx))
        n_mul.operation = "MULTIPLY"
        n_mul.use_clamp = True
        glinks.new(n_bw.outputs["Val"],             n_mul.inputs[0])
        glinks.new(n_gin.outputs[zone_key],         n_mul.inputs[1])

        # Invert (Fac from group input)
        n_inv = nn(gnodes, "ShaderNodeInvert", x, y - 130,
                   "Invert {} {}".format(chain_name, zone_idx))
        glinks.new(n_gin.outputs[invert_key],       n_inv.inputs["Fac"])
        glinks.new(n_mul.outputs["Value"],          n_inv.inputs["Color"])

        # Mix
        n_mix = nn(gnodes, "ShaderNodeMix", x, y - 280,
                   "{} Mix {}".format(chain_name, zone_idx))
        n_mix.data_type    = "FLOAT"
        n_mix.blend_type   = "MIX"
        n_mix.clamp_factor = True

        # Factor
        glinks.new(n_gin.outputs[mask_sock_name], n_mix.inputs["Factor"])
        # A and B: in Blender 4.x ShaderNodeMix FLOAT mode,
        # sockets are named "A" and "B" but there are TWO pairs
        # (one for each data type). We must pick the FLOAT ones.
        # The FLOAT sockets are the ones of type NodeSocketFloat.
        float_socks = [s for s in n_mix.inputs
                       if s.name in ("A", "B") and s.type == "VALUE"]
        if len(float_socks) >= 2:
            glinks.new(prev_socket,            float_socks[0])
            glinks.new(n_inv.outputs["Color"], float_socks[1])
        else:
            # Fallback: index 2 and 3
            glinks.new(prev_socket,            n_mix.inputs[2])
            glinks.new(n_inv.outputs["Color"], n_mix.inputs[3])
        # Result float socket
        float_outs = [s for s in n_mix.outputs if s.type == "VALUE"]
        prev_socket = float_outs[0] if float_outs else n_mix.outputs[-1]

    return prev_socket


def _build_color_chain_inside(gnodes, glinks, n_gin,
                               mask_socket_names, x_start, y_base):
    """
    Subsurface color chain inside the group.
    """
    # Base color from group input
    prev_socket = n_gin.outputs["Subsurface Base"]

    for i, mask_sock_name in enumerate(mask_socket_names):
        zone_idx = i + 1
        x        = x_start + i * GX_STEP
        y        = y_base
        col_key  = "Subsurface Col {}".format(zone_idx)

        n_mix = nn(gnodes, "ShaderNodeMix", x, y,
                   "SUBSURFACE Mix {}".format(zone_idx))
        n_mix.data_type    = "RGBA"
        n_mix.blend_type   = "MIX"
        n_mix.clamp_factor = True

        glinks.new(n_gin.outputs[mask_sock_name],  n_mix.inputs["Factor"])
        glinks.new(prev_socket,                    n_mix.inputs["A"])
        glinks.new(n_gin.outputs[col_key],         n_mix.inputs["B"])

        prev_socket = n_mix.outputs["Result"]

    return prev_socket


# ---------------------------------------------------------------------------
# Main material builder (outside the group)
# ---------------------------------------------------------------------------

def build_material(obj, folder):
    tex            = find_textures(folder)
    n_masks        = len(tex["masks"])
    has_subsurface = tex["subsurface"] is not None

    if not tex["diffuse"]:
        return False, "No _diffuse file found."
    if not tex["normal"]:
        return False, "No _normal file found."

    mask_inv_flags = [inv for (_, inv, _idx) in tex["masks"]]

    # Build the node group
    grp = build_node_group(tex, n_masks, has_subsurface, mask_inv_flags)

    # Material
    mat_name = os.path.basename(os.path.normpath(folder)) or "FoodMaterial"
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

    # ------------------------------------------------------------------
    # 1. Image Texture nodes (outside)
    # ------------------------------------------------------------------

    n_diff = img_node(nodes, tex["diffuse"], "sRGB",
                      MX_TEX, MY_DIFFUSE, "Diffuse")
    n_norm = img_node(nodes, tex["normal"], "Non-Color",
                      MX_TEX, MY_NORMAL, "Normal Tex")

    n_plate = None
    if tex["mask_plate"]:
        n_plate = img_node(nodes, tex["mask_plate"], "Non-Color",
                           MX_TEX, MY_PLATE, "Mask Plate")

    mask_img_nodes = []
    for i, (path, inv, idx) in enumerate(tex["masks"]):
        y = MY_MASKS - i * 220
        n_tex = img_node(nodes, path, "Non-Color",
                         MX_TEX, y, "Mask_{}".format(idx))
        if inv:
            n_pre_inv = nn(nodes, "ShaderNodeInvert",
                           MX_TEX + 350, y, "Pre-Invert Mask_{}".format(idx))
            n_pre_inv.inputs["Fac"].default_value = 1.0
            links.new(n_tex.outputs["Color"], n_pre_inv.inputs["Color"])
            mask_img_nodes.append(n_pre_inv)
        else:
            mask_img_nodes.append(n_tex)

    n_sub_tex = None
    if has_subsurface:
        y = MY_MASKS - n_masks * 220 - 220
        n_sub_tex = img_node(nodes, tex["subsurface"], "sRGB",
                             MX_TEX, y, "Subsurface Tex")

    # ------------------------------------------------------------------
    # 2. Group node
    # ------------------------------------------------------------------

    n_grp = nn(nodes, "ShaderNodeGroup", MX_GRP, 0, "PBR Toolkit Controls")
    n_grp.node_tree = grp
    n_grp.width     = 280

    # Wire textures -> group inputs
    links.new(n_diff.outputs["Color"],  n_grp.inputs["Diffuse"])
    links.new(n_norm.outputs["Color"],  n_grp.inputs["Normal Tex"])

    if n_plate:
        links.new(n_plate.outputs["Color"], n_grp.inputs["Plate Mask"])

    for i, n_mask in enumerate(mask_img_nodes):
        links.new(n_mask.outputs["Color"],
                  n_grp.inputs["Mask {}".format(i + 1)])

    if n_sub_tex:
        links.new(n_sub_tex.outputs["Color"], n_grp.inputs["Subsurface Tex"])

    # ------------------------------------------------------------------
    # 3. Principled BSDF
    # ------------------------------------------------------------------

    n_bsdf = nn(nodes, "ShaderNodeBsdfPrincipled", MX_BSDF, 300, "Principled BSDF")
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

    # ------------------------------------------------------------------
    # 4. Material Output
    # ------------------------------------------------------------------

    n_out = nn(nodes, "ShaderNodeOutputMaterial", MX_OUT, 300, "Material Output")
    links.new(n_bsdf.outputs["BSDF"], n_out.inputs["Surface"])

    return True, mat_name


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class PBRTK_OT_SetupMaterial(Operator):
    bl_idname      = "pbrtk.setup_material"
    bl_label       = "Setup Material"
    bl_description = "Build PBR node graph - all processing inside node group"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self, context):
        props  = context.scene.pbrtk_material_props
        folder = bpy.path.abspath(props.texture_folder)

        if not folder or not os.path.isdir(folder):
            self.report({"ERROR"}, "Invalid texture folder.")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh first.")
            return {"CANCELLED"}

        ok, msg = build_material(obj, folder)
        if ok:
            self.report({"INFO"}, "Material '{}' created.".format(msg))
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class PBRTK_MaterialProperties(PropertyGroup):
    texture_folder: StringProperty(
        name="Texture Folder",
        description="Folder containing all textures for this dish",
        default="",
        subtype="DIR_PATH",
    )


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class PBRTK_PT_SetupPanel(Panel):
    bl_label       = "PBR Toolkit -- 4. Setup Material"
    bl_idname      = "PBRTK_PT_setup"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "PBR Toolkit"
    bl_order       = 2

    def draw(self, context):
        layout = self.layout
        props  = context.scene.pbrtk_material_props

        layout.label(text="Texture folder:")
        layout.prop(props, "texture_folder", text="")

        obj = context.active_object
        if obj and obj.type == "MESH":
            layout.label(text="Mesh: {}".format(obj.name), icon="MESH_DATA")
        else:
            layout.label(text="Select a mesh first", icon="ERROR")

        layout.separator()
        layout.operator("pbrtk.setup_material", icon="NODETREE")

        layout.separator()
        layout.label(text="Group inputs (fixed):", icon="INFO")
        col = layout.column(align=True)
        col.scale_y = 0.7
        for line in [
            "Hue / Saturation / Value",
            "Normal Strength / Bump Strength",
        ]:
            col.label(text=line)

        layout.label(text="Per zone (x N masks):", icon="INFO")
        col2 = layout.column(align=True)
        col2.scale_y = 0.7
        for line in [
            "Roughness Zone N  (0-2)",
            "Rough Invert N    (0=off 1=on)",
            "Specular Zone N   (0-2)",
            "Spec Invert N     (0=off 1=on)",
            "Subsurface Col N  (color)",
        ]:
            col2.label(text=line)

        layout.separator()
        layout.label(text="Naming convention:", icon="INFO")
        col3 = layout.column(align=True)
        col3.scale_y = 0.7
        for line in [
            "{dish}_diffuse.png",
            "{dish}_normal.png",
            "{dish}_mask_plate.png",
            "{dish}_mask_1.png",
            "{dish}_mask_1_inv.png (inverted)",
            "{dish}_subsurface.png (optional)",
        ]:
            col3.label(text=line)


classes = (
    PBRTK_MaterialProperties,
    PBRTK_OT_SetupMaterial,
    PBRTK_PT_SetupPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pbrtk_material_props = bpy.props.PointerProperty(
        type=PBRTK_MaterialProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pbrtk_material_props
