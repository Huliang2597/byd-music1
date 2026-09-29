"""折中方案第 1 步：用 Blender 渲出带描边的三渲二素材（透明背景 PNG），动画交给 pv2d.py（SVG）。

输出:
  rose_<颜色>_<仰角>_<阶段>.png   玫瑰（锚点 = 图片中心 = 花托；图片上方 = 花轴方向）
  planet_<角度>.png               星球自转一圈（无花），planet_hd.png 为推近用的高清图
  door.png                        未知之门（正面略俯视，锚点在底部中心）

用法: python3 sprites.py <输出目录> [roses|planet|door|all]
"""
import math
import os
import sys
import time

import bpy  # noqa: I001
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene as S  # noqa: E402

ROSE_ELEV = [90, 55, 25]
ROSE_STAGES = [0.05, 0.4, 0.75, 1.0]
PLANET_STEP = 5
PLANET_CAM_ELEV = 20  # 星球素材的观察仰角，pv2d.py 投影时必须一致
PLANET_FINE = range(280, 346)  # 动画实际用到的自转角度，逐度渲染
HD_ANGLE = 280  # 高清图：贴地镜头那片花田（纬 18° 经 -8°）正对镜头


def setup(res):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = 12
    c.use_adaptive_sampling = False
    c.use_denoising = False
    c.max_bounces = 8
    c.diffuse_bounces = c.glossy_bounces = c.transmission_bounces = c.volume_bounces = 0
    c.transparent_max_bounces = 12
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    S.params_group()
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.rotation_mode = "QUATERNION"
    sc.camera = cam
    ink = bpy.data.collections.new("Ink")
    sc.collection.children.link(ink)
    return sc, cam, ink


def freestyle(sc, ink, thickness):
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    sc.render.line_thickness = 1.0
    fs = sc.view_layers[0].freestyle_settings
    ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("ink")
    ls.select_by_collection = True
    ls.collection = ink
    ls.select_silhouette = ls.select_border = True
    ls.select_crease = False
    ls.linestyle = ls.linestyle or bpy.data.linestyles.new("ink")
    ls.linestyle.color = (0.05, 0.18, 0.24)
    ls.linestyle.thickness = thickness


def aim(cam, loc, target, up):
    loc, target = Vector(loc), Vector(target)
    fwd = (target - loc).normalized()
    right = fwd.cross(up).normalized()
    cam_up = right.cross(fwd)
    cam.location = loc
    cam.rotation_quaternion = Matrix((right, cam_up, -fwd)).transposed().to_quaternion()
    m = cam.rotation_quaternion.to_matrix()
    light = (m.col[0] * -0.55 + m.col[1] * 0.65 + m.col[2] * 0.5).normalized()
    node = bpy.data.node_groups["ToonParams"].nodes["light"]
    for i in range(3):
        node.inputs[i].default_value = light[i]


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def roses(out):
    sc, cam, ink = setup(512)
    freestyle(sc, ink, 2.2)
    cam.data.ortho_scale = 2.9
    mats = [S.toon_material(f"Petal_{c}", color=S.PALETTE[c], two_sided=True, rim_strength=0.3) for c in S.PETAL_COLORS]
    leaf_mat = S.toon_material("Leaf", color=S.PALETTE["leaf"], two_sided=True, rim_strength=0.2)
    phi, layer = [], []
    for li, (n, _, _, _, off) in enumerate(S.ROSE_LAYERS):
        for k in range(n):
            phi.append(math.radians(off) + k * 2 * math.pi / n)
            layer.append(li)
    phi, layer = np.array(phi), np.array(layer)
    scale_l = np.array([S.ROSE_LAYERS[i][1] for i in layer])
    closed = np.radians([S.ROSE_LAYERS[i][2] for i in layer])
    opened = np.radians([S.ROSE_LAYERS[i][3] for i in layer])
    v, f = S.petal_geometry(nu=6, nv=4)
    rose = S.InstancedMesh("rose", v, f, [0] * len(phi), [mats[0]], ink)
    lv, lf = S.petal_geometry(length=1.25, width=0.3, cup=0.12, curl=0.05, nu=5, nv=2)
    leaves = S.InstancedMesh("leaves", lv, lf, [0, 0], [leaf_mat], ink)
    leaves.update(S.rot_zx(np.array([0.4, 3.4]), np.radians([10.0, 10.0])), np.ones(2), np.zeros((2, 3)))
    for stage in ROSE_STAGES:
        tilt = closed + (opened - closed) * stage
        rose.update(S.rot_zx(phi, tilt), scale_l * (0.7 + 0.3 * stage), np.zeros((len(phi), 3)))
        for elev in ROSE_ELEV:
            e = math.radians(elev)
            if elev == 90:
                aim(cam, (0, 0, 10), (0, 0, 0), Vector((0, 1, 0)))
            else:
                aim(cam, (0, -10 * math.cos(e), 10 * math.sin(e)), (0, 0, 0), Vector((0, 0, 1)))
            for ci, c in enumerate(S.PETAL_COLORS):
                rose.me.materials[0] = mats[ci]
                path = os.path.join(out, f"rose_{c}_{elev}_{stage:.2f}.png")
                if not os.path.exists(path):
                    t0 = time.time()
                    render(sc, path)
                    print(os.path.basename(path), f"{time.time() - t0:.1f}s", flush=True)


def planet(out):
    sc, cam, ink = setup(1024)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1.0)
    p = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    p.data.materials.append(S.toon_material("Planet", albedo_fn=S.planet_albedo, rim_strength=0.65))
    # 星球材质用 Object 坐标取噪声：半径 1 时要放大 4 倍才与原场景一致
    for n in p.data.materials[0].node_tree.nodes:
        if n.type == "TEX_NOISE":
            n.inputs["Scale"].default_value = 0.55 * S.R
    S.add_outline(p, 0.0125, S.outline_material())
    cam.data.ortho_scale = 2.08
    e = math.radians(PLANET_CAM_ELEV)
    aim(cam, (0, -10 * math.cos(e), 10 * math.sin(e)), (0, 0, 0), Vector((0, 0, 1)))
    p.rotation_mode = "XYZ"
    for ang in sorted(set(range(0, 360, PLANET_STEP)) | set(PLANET_FINE)):
        path = os.path.join(out, f"planet_{ang:03d}.png")
        if os.path.exists(path):
            continue
        p.rotation_euler = (0, 0, math.radians(ang))
        render(sc, path)
        print(os.path.basename(path), flush=True)
    sc.render.resolution_x = sc.render.resolution_y = 2560
    p.rotation_euler = (0, 0, math.radians(HD_ANGLE))
    path = os.path.join(out, "planet_hd.png")
    if not os.path.exists(path):
        render(sc, path)


def door(out):
    sc, cam, ink = setup(1024)
    freestyle(sc, ink, 2.5)
    mat_stone = S.toon_material("Stone", color=S.PALETTE["stone"], rim_strength=0.5)
    mat_gold = S.toon_material("Gold", color=S.PALETTE["gold"], rim_strength=0.6)
    objs = []
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.1, depth=1.1, location=(side * 0.55, 0, 0.55))
        objs.append(bpy.context.active_object)
        objs[-1].data.materials.append(mat_stone)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.55, minor_radius=0.085, major_segments=64, minor_segments=16,
                                     location=(0, 0, 1.1), rotation=(math.radians(90), 0, 0))
    arch = bpy.context.active_object
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(arch.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -0.01], context="VERTS")
    bm.to_mesh(arch.data)
    bm.free()
    arch.data.materials.append(mat_gold)
    objs.append(arch)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.95, depth=0.12)
    objs.append(bpy.context.active_object)
    objs[-1].data.materials.append(mat_stone)
    me = bpy.data.meshes.new("portal")
    pts = [(0.47 * math.cos(a), 0, 1.1 + 0.47 * math.sin(a)) for a in np.linspace(0, math.pi, 24)]
    pts += [(-0.47, 0, 0.05), (0.47, 0, 0.05)]
    me.from_pydata(pts, [], [list(range(len(pts)))])
    me.materials.append(S.glow_material("Portal", (0.85, 1.0, 0.97), 1.4))
    portal = bpy.data.objects.new("portal", me)
    sc.collection.objects.link(portal)
    for o in objs:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_smooth()
        for cl in list(o.users_collection):
            cl.objects.unlink(o)
        ink.objects.link(o)
    cam.data.ortho_scale = 2.4
    e = math.radians(12)
    aim(cam, (0, -10 * math.cos(e), 0.8 + 10 * math.sin(e)), (0, 0, 0.8), Vector((0, 0, 1)))
    render(sc, os.path.join(out, "door.png"))


if __name__ == "__main__":
    out = os.path.abspath(sys.argv[1])
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    os.makedirs(out, exist_ok=True)
    {"roses": roses, "planet": planet, "door": door}.get(what, lambda o: (roses(o), planet(o), door(o)))(out)
