"""
camera_contract.py — geometric contract carried by the persistent ortho camera.

Single source of truth between step 1 (render, which writes it) and step 3
(reprojection, which reads it). Stored as custom properties on the camera object.
"""

from dataclasses import dataclass

K_MESH   = "pbrtk_target_mesh"
K_BASE   = "pbrtk_base_name"
K_CX     = "pbrtk_center_x"
K_CY     = "pbrtk_center_y"
K_EXTENT = "pbrtk_extent"
K_RES    = "pbrtk_resolution"
K_ZMAX   = "pbrtk_z_max"

_REQUIRED = (K_MESH, K_CX, K_CY, K_EXTENT)


@dataclass
class CameraContract:
    target_mesh: str
    base_name: str
    center_x: float
    center_y: float
    extent: float
    resolution: int
    z_max: float


def write(cam_obj, contract):
    cam_obj[K_MESH]   = contract.target_mesh
    cam_obj[K_BASE]   = contract.base_name
    cam_obj[K_CX]     = contract.center_x
    cam_obj[K_CY]     = contract.center_y
    cam_obj[K_EXTENT] = contract.extent
    cam_obj[K_RES]    = contract.resolution
    cam_obj[K_ZMAX]   = contract.z_max


def has_contract(obj):
    return (obj is not None and obj.type == "CAMERA"
            and all(k in obj for k in _REQUIRED))


def read(cam_obj):
    return CameraContract(
        target_mesh=cam_obj[K_MESH],
        base_name=cam_obj.get(K_BASE, ""),
        center_x=float(cam_obj[K_CX]),
        center_y=float(cam_obj[K_CY]),
        extent=float(cam_obj[K_EXTENT]),
        resolution=int(cam_obj.get(K_RES, 0)),
        z_max=float(cam_obj.get(K_ZMAX, 0.0)),
    )
