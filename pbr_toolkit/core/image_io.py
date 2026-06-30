"""
image_io.py — I/O image mutualisée.

Lecture/écriture des pixels via foreach_get/foreach_set (rapide, vs le
marshalling Python de img.pixels[:], prohibitif en 4K/8K).
"""

import os
import numpy as np
import bpy


def load_gray(path):
    """
    Charge une image en niveaux de gris (canal R), orientée top-down.
    Retourne (array HxW float32, w, h) ou (None, 0, 0) si invalide.
    """
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        if w == 0 or h == 0:
            return None, 0, 0
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        gray = buf.reshape(h, w, 4)[:, :, 0]
        # Blender charge bottom-up : on flip pour avoir y=0 en haut.
        return np.ascontiguousarray(np.flipud(gray)), w, h
    finally:
        bpy.data.images.remove(img)


def save_gray_png(arr, path):
    """Sauve un array (H, W) float32 [0,1] en PNG niveaux de gris RGB."""
    h, w = arr.shape
    rgba = np.empty((h, w, 4), dtype=np.float32)
    rgba[:, :, 0] = arr
    rgba[:, :, 1] = arr
    rgba[:, :, 2] = arr
    rgba[:, :, 3] = 1.0
    img = bpy.data.images.new("__pbrtk_tmp__", width=w, height=h,
                              alpha=False, float_buffer=False)
    try:
        # Blender stocke bottom-up : on flip avant écriture.
        flat = np.ascontiguousarray(np.flipud(rgba).ravel(), dtype=np.float32)
        img.pixels.foreach_set(flat)
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def load_datablock(path, colorspace="sRGB"):
    """Charge (ou réutilise) une image data-block pour un node Image Texture."""
    name = os.path.basename(path)
    if name in bpy.data.images:
        return bpy.data.images[name]
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = colorspace
    return img
