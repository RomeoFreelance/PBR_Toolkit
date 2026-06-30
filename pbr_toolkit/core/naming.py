"""
naming.py — convention de nommage du pipeline, source unique de vérité.

Tout est dérivé d'un dossier projet unique et d'un « nom de base » (par défaut
le nom du mesh actif). Générique : aucune hypothèse métier.

  {base}_diffuse.png         albedo / base color          (requis material)
  {base}_normal.png          normal map tangente          (requis material)
  {base}_subsurface.png      carte subsurface             (option)
  {base}_topview.png         rendu top-view               (étape 1)
  {base}_mask_plate.png      masque "plate" espace-image  (étape 2, option)
  {base}_mask_<n>.png        masque de zone espace-image  (étape 2)
  {base}_mask_*_uv.png       masque reprojeté espace-UV   (étape 3 → material)
  ..._inv...                 variante pré-inversée
"""

import os
import re

IMG_EXTS = (".png", ".tif", ".tiff", ".exr", ".jpg", ".jpeg")

_NUM_MASK_RE = re.compile(r"_mask_(\d+)", re.IGNORECASE)
_PLATE_RE    = re.compile(r"_mask_plate", re.IGNORECASE)
_UV_RE       = re.compile(r"_uv(?=\.|_|$)", re.IGNORECASE)
_INV_RE      = re.compile(r"_inv(?=\.|_|$)", re.IGNORECASE)


def resolve_base_name(settings, context):
    """Nom de base : champ explicite, sinon nom du mesh actif."""
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
    """Chemin de sortie reprojeté : insère _uv et force .png."""
    d, fname = os.path.split(src_path)
    stem, _ext = os.path.splitext(fname)
    return os.path.join(out_folder or d, f"{stem}_uv.png")


def list_source_masks(folder, base):
    """
    Masques espace-image à reprojeter pour cet asset : numérotés + plate,
    en excluant ceux déjà reprojetés (_uv). Triés par index (plate en tête).
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
    Textures consommées par le material : diffuse/normal/subsurface +
    masques espace-UV uniquement (_uv). Le plate-mask UV alimente le Coat.
    """
    result = {
        "diffuse":    None,
        "normal":     None,
        "subsurface": None,
        "mask_plate": None,
        "masks":      [],   # liste de (path, inverted, idx)
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
