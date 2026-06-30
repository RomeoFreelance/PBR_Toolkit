"""
image_io.py — shared image I/O.

Pixel read/write through foreach_get/foreach_set (fast, versus the Python-level
marshalling of img.pixels[:], which is prohibitive at 4K/8K).
"""

import os
import numpy as np
import bpy


def load_gray(path):
    """
    Load an image as grayscale (R channel), oriented top-down.
    Returns (HxW float32 array, w, h) or (None, 0, 0) if invalid.
    """
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        if w == 0 or h == 0:
            return None, 0, 0
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        gray = buf.reshape(h, w, 4)[:, :, 0]
        # Blender loads bottom-up: flip so y=0 is at the top.
        return np.ascontiguousarray(np.flipud(gray)), w, h
    finally:
        bpy.data.images.remove(img)


def save_gray_png(arr, path):
    """Save an (H, W) float32 [0,1] array as a grayscale RGB PNG."""
    h, w = arr.shape
    rgba = np.empty((h, w, 4), dtype=np.float32)
    rgba[:, :, 0] = arr
    rgba[:, :, 1] = arr
    rgba[:, :, 2] = arr
    rgba[:, :, 3] = 1.0
    img = bpy.data.images.new("__pbrtk_tmp__", width=w, height=h,
                              alpha=False, float_buffer=False)
    try:
        # Blender stores bottom-up: flip before writing.
        flat = np.ascontiguousarray(np.flipud(rgba).ravel(), dtype=np.float32)
        img.pixels.foreach_set(flat)
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def load_datablock(path, colorspace="sRGB"):
    """Load (or reuse) an image data-block for an Image Texture node."""
    name = os.path.basename(path)
    if name in bpy.data.images:
        return bpy.data.images[name]
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = colorspace
    return img
