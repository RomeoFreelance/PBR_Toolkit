"""
naming.py — single source of truth for the pipeline naming convention.

Everything is derived from a single project folder and a "base name" (the
active mesh name by default). Generic: no domain-specific assumptions.

  {base}_diffuse.png         albedo / base color          (material, required)
  {base}_normal.png          tangent-space normal map     (material, required)
  {base}_subsurface.png      subsurface map               (optional)
  {base}_topview.png         top-view render              (step 1)
  {base}_mask_plate.png      "plate" mask, image-space    (step 2, optional)
  {base}_mask_<n>.png        zone mask, image-space       (step 2)
  {base}_mask_*_uv.png       reprojected mask, UV-space   (step 3 -> material)
  ..._inv...                 pre-inverted variant
"""

import os
import re

IMG_EXTS = (".png", ".tif", ".tiff", ".exr", ".jpg", ".jpeg")

_NUM_MASK_RE = re.compile(r"_mask_(\d+)", re.IGNORECASE)
_PLATE_RE    = re.compile(r"_mask_plate", re.IGNORECASE)
_UV_RE       = re.compile(r"_uv(?=\.|_|$)", re.IGNORECASE)
_INV_RE      = re.compile(r"_inv(?=\.|_|$)", re.IGNORECASE)


def resolve_base_name(settings, context):
    """Base name: explicit field, otherwise the active mesh name."""
    name = (settings.base_name or "").strip()
    if name:
        return name
    obj = context.active_object
    return obj.name if (obj and obj.type == "MESH") else ""


def is_image_file(fname):
    return os.path.splitext(fname)[1].lower() in IMG_EXTS


def topview_stem(base):
    return f"{base}_topview"


def topview_filename(base):
    return f"{topview_stem(base)}.png"


def uv_output_path(src_path, out_folder=None):
    """Reprojected output path: insert _uv and force .png."""
    d, fname = os.path.split(src_path)
    stem, _ext = os.path.splitext(fname)
    return os.path.join(out_folder or d, f"{stem}_uv.png")


def list_source_masks(folder, base):
    """
    Image-space masks to reproject for this asset: numbered + plate, excluding
    already-reprojected ones (_uv). Sorted by index (plate first).
    """
    prefix = f"{base}_mask_".lower()
    found = []
    for f in os.listdir(folder):
        if not is_image_file(f):
            continue
        fl = f.lower()
        if not fl.startswith(prefix) or _UV_RE.search(fl):
            continue
        num = _NUM_MASK_RE.search(fl)
        if num:
            order = int(num.group(1))
        elif _PLATE_RE.search(fl):
            order = -1
        else:
            continue
        found.append((order, os.path.join(folder, f)))
    found.sort(key=lambda t: t[0])
    return [p for _, p in found]


def find_uv_textures(folder, base):
    """
    Textures consumed by the material: diffuse/normal/subsurface + UV-space
    masks only (_uv). The UV plate mask feeds the Coat output.
    """
    result = {
        "diffuse":    None,
        "normal":     None,
        "subsurface": None,
        "mask_plate": None,
        "masks":      [],   # list of (path, inverted, idx)
    }
    bl = base.lower()
    raw = []
    for f in os.listdir(folder):
        if not is_image_file(f):
            continue
        fl = f.lower()
        if not fl.startswith(bl):
            continue
        path = os.path.join(folder, f)
        if "_diffuse." in fl:
            result["diffuse"] = path
        elif "_normal." in fl:
            result["normal"] = path
        elif "_subsurface." in fl:
            result["subsurface"] = path
        elif _PLATE_RE.search(fl) and _UV_RE.search(fl):
            result["mask_plate"] = path
        else:
            num = _NUM_MASK_RE.search(fl)
            if num and _UV_RE.search(fl):
                raw.append((int(num.group(1)), path, _INV_RE.search(fl) is not None))
    raw.sort(key=lambda t: t[0])
    result["masks"] = [(p, inv, idx) for (idx, p, inv) in raw]
    return result
