"""《Blooming Planet》三渲二 PV：用 bpy 程序化搭建场景并逐帧渲染（Cycles，自发光卡通着色）。

所有花 / 飞舞的花瓣各合并成一个网格，每帧用 numpy 直接改顶点，避免上千个对象拖慢 Cycles 同步。

用法:
  python3 scene.py <features.npz> <输出目录> --start 秒 --end 秒 [--fps 24] [--still 秒,...] [--scale 100] [--part i/n]
"""
import argparse
import math
import os
import random
import time

import bpy  # noqa: I001  bpy 必须先于 bmesh 导入
import bmesh
import numpy as np
from mathutils import Matrix, Vector

R = 4.0  # 星球半径

# 配色取自专辑封面
PALETTE = {
    "sea": (0.10, 0.52, 0.56),
    "land": (0.47, 0.84, 0.70),
    "land2": (0.30, 0.70, 0.62),
    "sand": (0.86, 0.95, 0.86),
    "white": (0.95, 0.98, 1.0),
    "paleblue": (0.66, 0.82, 1.0),
    "blue": (0.30, 0.47, 0.93),
    "mint": (0.62, 0.92, 0.82),
    "pink": (0.98, 0.78, 0.86),
    "cream": (1.0, 0.90, 0.66),
    "gold": (0.93, 0.78, 0.48),
    "stone": (0.86, 0.91, 0.95),
    "leaf": (0.24, 0.64, 0.50),
}
PETAL_COLORS = ["white", "paleblue", "blue", "mint", "pink", "cream"]
PETAL_WEIGHTS = [0.30, 0.26, 0.20, 0.12, 0.06, 0.06]

# 歌词时间（秒）
T_LINE1, T_LINE2, T_LINE3, T_LINE4 = 218.21, 222.83, 228.19, 232.86
T_MEET = 226.30  # 两颗光相会
T_THROUGH = 232.60  # 穿过门

# 玫瑰状花型：(片数, 缩放, 含苞仰角°, 盛开仰角°, 起始角°)
ROSE_LAYERS = [(5, 1.00, 78, 14, 0), (5, 0.80, 84, 38, 36), (4, 0.60, 88, 60, 12), (3, 0.40, 90, 76, 50)]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


def sph(lat, lon, r=R):
    la, lo = math.radians(lat), math.radians(lon)
    return Vector((r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la)))


def basis_from(normal, hint=Vector((0, 0, 1))):
    """以 normal 为 Z 轴的正交基 (x, y, z)。"""
    z = normal.normalized()
    x = hint.cross(z)
    if x.length < 1e-4:
        x = Vector((1, 0, 0)).cross(z)
    x.normalize()
    y = z.cross(x)
    return x, y, z


# ================================================================ materials


def params_group():
    """所有材质共用的“光照方向 / 发光”参数，逐帧更新。"""
    g = bpy.data.node_groups.new("ToonParams", "ShaderNodeTree")
    g.interface.new_socket("Light", in_out="OUTPUT", socket_type="NodeSocketVector")
    g.interface.new_socket("Glow", in_out="OUTPUT", socket_type="NodeSocketFloat")
    out = g.nodes.new("NodeGroupOutput")
    comb = g.nodes.new("ShaderNodeCombineXYZ")
    comb.name = "light"
    glow = g.nodes.new("ShaderNodeValue")
    glow.name = "glow"
    g.links.new(comb.outputs[0], out.inputs["Light"])
    g.links.new(glow.outputs[0], out.inputs["Glow"])
    return g


def new_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree.nodes, m.node_tree.links


def toon_material(name, albedo_fn=None, color=(1, 1, 1), shadow=(0.52, 0.60, 0.88), highlight=(1.12, 1.12, 1.10),
                  rim=(0.78, 1.0, 0.97), rim_strength=0.5, glow_gain=0.0, two_sided=False):
    """赛璐璐着色：N·L 分成阴影 / 亮部 / 高光三段，再叠加边缘光；只输出自发光。"""
    m, N, L = new_material(name)
    out = N.new("ShaderNodeOutputMaterial")
    params = N.new("ShaderNodeGroup")
    params.node_tree = bpy.data.node_groups["ToonParams"]
    geo = N.new("ShaderNodeNewGeometry")
    normal = geo.outputs["Normal"]
    if two_sided:  # 薄片背面翻转法线
        sign = N.new("ShaderNodeMath")
        sign.operation = "MULTIPLY_ADD"
        sign.inputs[1].default_value = -2.0
        sign.inputs[2].default_value = 1.0
        L.new(geo.outputs["Backfacing"], sign.inputs[0])
        flip = N.new("ShaderNodeVectorMath")
        flip.operation = "SCALE"
        L.new(geo.outputs["Normal"], flip.inputs[0])
        L.new(sign.outputs[0], flip.inputs["Scale"])
        normal = flip.outputs[0]
    dot = N.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L.new(normal, dot.inputs[0])
    L.new(params.outputs["Light"], dot.inputs[1])
    fac = N.new("ShaderNodeMath")
    fac.operation = "MULTIPLY_ADD"
    fac.inputs[1].default_value = 0.5
    fac.inputs[2].default_value = 0.5
    L.new(dot.outputs["Value"], fac.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*shadow, 1)
    el[1].position, el[1].color = 0.49, (1, 1, 1, 1)
    hi = el.new(0.955)
    hi.color = (*highlight, 1)
    L.new(fac.outputs[0], ramp.inputs["Fac"])
    if albedo_fn is not None:
        albedo = albedo_fn(N, L)
    else:
        rgb = N.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (*color, 1)
        albedo = rgb.outputs[0]
    mul = N.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    L.new(albedo, mul.inputs[0])
    L.new(ramp.outputs["Color"], mul.inputs[1])
    emit = N.new("ShaderNodeEmission")
    L.new(mul.outputs[0], emit.inputs["Color"])
    strength = N.new("ShaderNodeMath")
    strength.operation = "MULTIPLY_ADD"
    strength.inputs[1].default_value = glow_gain
    strength.inputs[2].default_value = 1.0
    L.new(params.outputs["Glow"], strength.inputs[0])
    L.new(strength.outputs[0], emit.inputs["Strength"])
    # 边缘光（只在朝光一侧）
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    rim_ramp = N.new("ShaderNodeValToRGB")
    rim_ramp.color_ramp.interpolation = "CONSTANT"
    rim_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    rim_ramp.color_ramp.elements[1].position = 0.72
    rim_ramp.color_ramp.elements[1].color = (rim_strength,) * 3 + (1,)
    L.new(lw.outputs["Facing"], rim_ramp.inputs["Fac"])
    mask = N.new("ShaderNodeMath")
    mask.operation = "GREATER_THAN"
    mask.inputs[1].default_value = -0.35
    L.new(dot.outputs["Value"], mask.inputs[0])
    amt = N.new("ShaderNodeVectorMath")
    amt.operation = "SCALE"
    L.new(rim_ramp.outputs["Color"], amt.inputs[0])
    L.new(mask.outputs[0], amt.inputs["Scale"])
    rim_col = N.new("ShaderNodeVectorMath")
    rim_col.operation = "MULTIPLY"
    rim_col.inputs[1].default_value = rim
    L.new(amt.outputs[0], rim_col.inputs[0])
    rim_emit = N.new("ShaderNodeEmission")
    L.new(rim_col.outputs[0], rim_emit.inputs["Color"])
    add = N.new("ShaderNodeAddShader")
    L.new(emit.outputs[0], add.inputs[0])
    L.new(rim_emit.outputs[0], add.inputs[1])
    L.new(add.outputs[0], out.inputs["Surface"])
    return m


def outline_material(color=(0.03, 0.14, 0.18)):
    """反向外壳描边：正面透明，背面（外壳内侧）显示描边色。"""
    m, N, L = new_material("Outline")
    out = N.new("ShaderNodeOutputMaterial")
    geo = N.new("ShaderNodeNewGeometry")
    emit = N.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1)
    transp = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    L.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    L.new(emit.outputs[0], mix.inputs[1])
    L.new(transp.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


def glow_material(name, color, strength=4.0):
    m, N, L = new_material(name)
    out = N.new("ShaderNodeOutputMaterial")
    emit = N.new("ShaderNodeEmission")
    emit.name = "emit"
    emit.inputs["Color"].default_value = (*color, 1)
    emit.inputs["Strength"].default_value = strength
    L.new(emit.outputs[0], out.inputs["Surface"])
    return m


def soft_material(name, color, strength, stops):
    """按朝向（Facing）控制不透明度的柔光材质。stops: [(facing, alpha), ...]"""
    m, N, L = new_material(name)
    out = N.new("ShaderNodeOutputMaterial")
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    ramp = N.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = stops[0][0], (stops[0][1],) * 3 + (1,)
    el[1].position, el[1].color = stops[1][0], (stops[1][1],) * 3 + (1,)
    for pos, a in stops[2:]:
        e = el.new(pos)
        e.color = (a, a, a, 1)
    L.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    emit = N.new("ShaderNodeEmission")
    emit.name = "emit"
    emit.inputs["Color"].default_value = (*color, 1)
    emit.inputs["Strength"].default_value = strength
    transp = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    L.new(ramp.outputs["Color"], mix.inputs["Fac"])
    L.new(transp.outputs[0], mix.inputs[1])
    L.new(emit.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


def planet_albedo(N, L):
    tc = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.55
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.55
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*PALETTE["sea"], 1)
    el[1].position, el[1].color = 0.47, (*PALETTE["sand"], 1)
    e2 = el.new(0.495)
    e2.color = (*PALETTE["land"], 1)
    e3 = el.new(0.62)
    e3.color = (*PALETTE["land2"], 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    return ramp.outputs["Color"]


# ================================================================ geometry helpers


def add_outline(obj, thickness, mat_outline):
    obj.data.materials.append(mat_outline)
    mod = obj.modifiers.new("outline", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(obj.data.materials) - 1


def petal_geometry(length=1.0, width=0.5, cup=0.22, curl=0.14, nu=9, nv=6):
    """花瓣（沿 +Y 伸出、法线朝 +Z），返回 (顶点 (V,3), 四边形面)。"""
    verts = []
    for iu in range(nu + 1):
        u = iu / nu
        w = width * (math.sin(math.pi * min(u * 1.08, 1.0)) ** 0.6) * (1 - 0.15 * u) + 0.02
        for iv in range(nv + 1):
            v = iv / nv * 2 - 1
            verts.append((v * w, u * length, cup * v * v * math.sin(math.pi * min(u, 0.95)) + curl * u * u))
    faces = []
    for iu in range(nu):
        for iv in range(nv):
            a = iu * (nv + 1) + iv
            faces.append((a, a + 1, a + nv + 2, a + nv + 1))
    return np.array(verts, dtype=np.float64), faces


def rot_zx(phi, tilt):
    """Rz(phi) @ Rx(tilt)，批量。phi, tilt: (P,) → (P,3,3)"""
    cp, sp, ct, st = np.cos(phi), np.sin(phi), np.cos(tilt), np.sin(tilt)
    m = np.zeros((len(phi), 3, 3))
    m[:, 0, 0], m[:, 0, 1], m[:, 0, 2] = cp, -sp * ct, sp * st
    m[:, 1, 0], m[:, 1, 1], m[:, 1, 2] = sp, cp * ct, -cp * st
    m[:, 2, 1], m[:, 2, 2] = st, ct
    return m


def euler_xyz(rx, ry, rz):
    """Blender XYZ 欧拉角 → 旋转矩阵，批量 (P,3,3)。"""
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    m = np.zeros((len(rx), 3, 3))
    m[:, 0, 0] = cy * cz
    m[:, 0, 1] = sx * sy * cz - cx * sz
    m[:, 0, 2] = cx * sy * cz + sx * sz
    m[:, 1, 0] = cy * sz
    m[:, 1, 1] = sx * sy * sz + cx * cz
    m[:, 1, 2] = cx * sy * sz - sx * cz
    m[:, 2, 0] = -sy
    m[:, 2, 1] = sx * cy
    m[:, 2, 2] = cx * cy
    return m


class InstancedMesh:
    """把同一片几何体的 P 个实例合并成一个网格，每帧只更新顶点坐标。"""

    def __init__(self, name, base_verts, base_faces, mat_index, materials, coll):
        self.base = base_verts
        self.P = len(mat_index)
        V = len(base_verts)
        faces = []
        for p in range(self.P):
            off = p * V
            faces.extend(tuple(i + off for i in f) for f in base_faces)
        me = bpy.data.meshes.new(name)
        me.from_pydata(np.zeros((self.P * V, 3)).tolist(), [], faces)
        for m in materials:
            me.materials.append(m)
        idx = np.repeat(np.asarray(mat_index, dtype=np.int32), len(base_faces))
        me.polygons.foreach_set("material_index", idx)
        me.shade_smooth()
        self.me = me
        self.obj = bpy.data.objects.new(name, me)
        coll.objects.link(self.obj)

    def update(self, rot, scale, pos):
        """rot: (P,3,3)，scale: (P,)，pos: (P,3)"""
        co = np.einsum("pij,vj->pvi", rot * scale[:, None, None], self.base) + pos[:, None, :]
        self.me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.me.update()


# ================================================================ scene


class PV:
    def __init__(self, features, fps):
        self.fps = fps
        d = np.load(features)
        self.kick = d["kick"]
        self.n = int(d["n_frames"])
        self.rnd = random.Random(7)
        self.build()

    def feature(self, arr, t):
        i = int(round(t * self.fps))
        return float(arr[min(max(i, 0), self.n - 1)])

    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        self.scene = sc
        sc.render.engine = "CYCLES"
        c = sc.cycles
        c.device = "CPU"
        c.samples = 8
        c.use_adaptive_sampling = False
        c.use_denoising = False
        c.max_bounces = 8
        c.diffuse_bounces = c.glossy_bounces = c.transmission_bounces = c.volume_bounces = 0
        c.transparent_max_bounces = 12
        for attr in ("filter_width", "pixel_filter_width"):
            if hasattr(c, attr):
                setattr(c, attr, 1.2)
        sc.render.use_persistent_data = True
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGB"
        sc.render.image_settings.compression = 15
        coll = sc.collection
        self.ink = bpy.data.collections.new("Ink")  # 参与 Freestyle 描边的物体
        coll.children.link(self.ink)
        self.params = params_group()
        self.build_world()
        self.setup_freestyle()

        self.mat_outline = outline_material()
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=R)
        planet = bpy.context.active_object
        planet.name = "planet"
        bpy.ops.object.shade_smooth()
        planet.data.materials.append(toon_material("Planet", albedo_fn=planet_albedo, rim_strength=0.65))
        add_outline(planet, 0.05, self.mat_outline)

        self.p0 = sph(18, -8).normalized()  # 贴地镜头的位置
        self.door_dir = sph(12, 150).normalized()
        self.build_flowers(coll)
        self.build_door(coll)
        self.build_orbs(coll)
        self.build_free_petals(coll)

        cam_data = bpy.data.cameras.new("cam")
        cam_data.clip_start = 0.02
        cam_data.clip_end = 400
        self.cam = bpy.data.objects.new("cam", cam_data)
        coll.objects.link(self.cam)
        self.cam.rotation_mode = "QUATERNION"
        sc.camera = self.cam

    def setup_freestyle(self):
        sc = self.scene
        sc.render.use_freestyle = True
        sc.render.line_thickness_mode = "ABSOLUTE"
        sc.render.line_thickness = 1.0
        fs = sc.view_layers[0].freestyle_settings
        fs.use_culling = True
        fs.crease_angle = math.radians(120)
        ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("ink")
        ls.select_by_visibility = True
        ls.select_by_collection = True
        ls.collection = self.ink
        ls.select_silhouette = True
        ls.select_border = True
        ls.select_crease = False
        ls.linestyle = ls.linestyle or bpy.data.linestyles.new("ink")
        ls.linestyle.color = (0.05, 0.18, 0.24)
        ls.linestyle.thickness = 1.5
        ls.linestyle.alpha = 0.9

    def build_world(self):
        world = bpy.data.worlds.new("World")
        self.scene.world = world
        world.use_nodes = True
        N, L = world.node_tree.nodes, world.node_tree.links
        N.clear()
        out = N.new("ShaderNodeOutputWorld")
        bg = N.new("ShaderNodeBackground")
        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ")
        L.new(tc.outputs["Generated"], sep.inputs[0])
        zmap = N.new("ShaderNodeMath")
        zmap.operation = "MULTIPLY_ADD"
        zmap.inputs[1].default_value = 0.5
        zmap.inputs[2].default_value = 0.5
        L.new(sep.outputs["Z"], zmap.inputs[0])
        grad = N.new("ShaderNodeValToRGB")
        el = grad.color_ramp.elements
        el[0].position, el[0].color = 0.2, (0.02, 0.05, 0.11, 1)
        el[1].position, el[1].color = 0.8, (0.06, 0.24, 0.32, 1)
        L.new(zmap.outputs[0], grad.inputs["Fac"])
        vor = N.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 160
        L.new(tc.outputs["Generated"], vor.inputs["Vector"])
        stars = N.new("ShaderNodeValToRGB")
        stars.color_ramp.elements[0].color = (1.5, 1.7, 1.7, 1)
        stars.color_ramp.elements[1].position = 0.04
        stars.color_ramp.elements[1].color = (0, 0, 0, 1)
        L.new(vor.outputs["Distance"], stars.inputs["Fac"])
        add = N.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        L.new(grad.outputs["Color"], add.inputs[0])
        L.new(stars.outputs["Color"], add.inputs[1])
        L.new(add.outputs[0], bg.inputs["Color"])
        L.new(bg.outputs[0], out.inputs["Surface"])

    def build_flowers(self, coll):
        rnd = self.rnd
        spots = []
        golden = math.pi * (3 - math.sqrt(5))
        n_uniform = 150
        for k in range(n_uniform):
            y = 1 - 2 * (k + 0.5) / n_uniform
            r = math.sqrt(1 - y * y)
            th = golden * k
            d = Vector((r * math.cos(th), r * math.sin(th), y))
            spots.append((d, rnd.uniform(0.2, 0.36), False))
        for _ in range(55):
            d = (self.p0 + Vector([rnd.gauss(0, 0.15) for _ in range(3)])).normalized()
            spots.append((d, rnd.uniform(0.14, 0.26), False))
        for lat, lon in [(32, 200), (-18, 232), (8, 258), (48, 238), (-42, 205), (18, 172), (-2, 215), (60, 150), (-60, 280)]:
            spots.append((sph(lat, lon).normalized(), rnd.uniform(0.95, 1.3), True))
        spots = [s for s in spots if (s[0] - self.door_dir).length > 0.3]
        self.flower_dir = np.array([tuple(s[0]) for s in spots])
        self.flower_giant = np.array([s[2] for s in spots])
        F = len(spots)
        self.F = F
        self.flower_phase = np.array([rnd.uniform(0, 6.28) for _ in range(F)])
        colors = rnd.choices(range(len(PETAL_COLORS)), weights=PETAL_WEIGHTS, k=F)
        # 每朵花的底座变换
        root_rot = np.zeros((F, 3, 3))
        for f, (d, size, _) in enumerate(spots):
            x, y, z = basis_from(d, Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 1)))
            root_rot[f] = np.array(Matrix((x, y, z)).transposed()) * size
        root_pos = self.flower_dir * (R - 0.02)
        # 花瓣实例表
        petal_f, petal_phi, petal_layer = [], [], []
        for f in range(F):
            base_ang = rnd.uniform(0, 6.28)
            for li, (n, _, _, _, off) in enumerate(ROSE_LAYERS):
                for k in range(n):
                    petal_f.append(f)
                    petal_phi.append(base_ang + math.radians(off) + k * 2 * math.pi / n + rnd.uniform(-0.12, 0.12))
                    petal_layer.append(li)
        self.petal_f = np.array(petal_f)
        self.petal_phi = np.array(petal_phi)
        layer = np.array(petal_layer)
        self.petal_scale_l = np.array([ROSE_LAYERS[i][1] for i in layer])
        self.petal_closed = np.radians([ROSE_LAYERS[i][2] for i in layer])
        self.petal_open = np.radians([ROSE_LAYERS[i][3] for i in layer])
        self.root_rot, self.root_pos = root_rot, root_pos
        verts, faces = petal_geometry(nu=6, nv=4)
        self.petal_mats = [toon_material(f"Petal_{c}", color=PALETTE[c], two_sided=True, glow_gain=0.9, rim_strength=0.3)
                           for c in PETAL_COLORS]
        self.flower_mesh = InstancedMesh("flowers", verts, faces, [colors[f] for f in petal_f], self.petal_mats, self.ink)
        # 叶子：静态，每朵花两片
        leaf_v, leaf_f = petal_geometry(length=1.25, width=0.3, cup=0.12, curl=0.05, nu=5, nv=2)
        lf, lphi = [], []
        for f in range(F):
            a = rnd.uniform(0, 6.28)
            lf += [f, f]
            lphi += [a, a + math.pi + rnd.uniform(-0.6, 0.6)]
        lf, lphi = np.array(lf), np.array(lphi)
        loc_rot = rot_zx(lphi, np.radians(np.full(len(lf), 10.0)))
        rot = np.einsum("pij,pjk->pik", root_rot[lf], loc_rot)
        leaves = InstancedMesh("leaves", leaf_v, leaf_f, [0] * len(lf),
                               [toon_material("Leaf", color=PALETTE["leaf"], two_sided=True, rim_strength=0.2)], self.ink)
        leaves.update(rot, np.ones(len(lf)), root_pos[lf])
        self.update_flowers(np.zeros(F), 0.0, 0.0)

    def update_flowers(self, bloom, t, sway):
        b = np.clip(bloom, 0, 1.15)[self.petal_f]
        tilt = self.petal_closed + (self.petal_open - self.petal_closed) * b
        tilt = tilt + sway * np.sin(t * 2.2 + self.flower_phase[self.petal_f] + self.petal_phi)
        loc_rot = rot_zx(self.petal_phi, tilt)
        rot = np.einsum("pij,pjk->pik", self.root_rot[self.petal_f], loc_rot)
        grow = 0.7 + 0.3 * np.clip(b, 0, 1)
        self.flower_mesh.update(rot, self.petal_scale_l * grow, self.root_pos[self.petal_f])

    def build_door(self, coll):
        d = self.door_dir
        x, _, up = basis_from(d)
        fwd = up.cross(x).normalized()
        self.door_x, self.door_up, self.door_forward = x, up, fwd
        root = bpy.data.objects.new("door", None)
        coll.objects.link(root)
        root.location = d * (R - 0.02)
        root.rotation_mode = "QUATERNION"
        root.rotation_quaternion = Matrix((x, fwd, up)).transposed().to_quaternion()
        root.scale = (0.6, 0.6, 0.6)
        self.door_center = d * (R - 0.02) + up * 0.6 * 0.75
        mat_stone = toon_material("Stone", color=PALETTE["stone"], rim_strength=0.5)
        mat_gold = toon_material("Gold", color=PALETTE["gold"], rim_strength=0.6)
        for side in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.1, depth=1.1)
            p = bpy.context.active_object
            bpy.ops.object.shade_smooth()
            p.data.materials.append(mat_stone)
            add_outline(p, 0.02, self.mat_outline)
            p.parent = root
            p.location = (side * 0.55, 0, 0.55)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.55, minor_radius=0.085, major_segments=64, minor_segments=16)
        arch = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(arch.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -0.01], context="VERTS")
        bm.to_mesh(arch.data)
        bm.free()
        bpy.ops.object.shade_smooth()
        arch.data.materials.append(mat_gold)
        add_outline(arch, 0.02, self.mat_outline)
        arch.parent = root
        arch.rotation_euler = (math.radians(90), 0, 0)
        arch.location = (0, 0, 1.1)
        me = bpy.data.meshes.new("portal")
        pts = [(0.47 * math.cos(a), 0, 1.1 + 0.47 * math.sin(a)) for a in np.linspace(0, math.pi, 24)]
        pts += [(-0.47, 0, 0.05), (0.47, 0, 0.05)]
        me.from_pydata(pts, [], [list(range(len(pts)))])
        self.mat_portal = glow_material("Portal", (0.85, 1.0, 0.97), 1.5)
        me.materials.append(self.mat_portal)
        portal = bpy.data.objects.new("portal", me)
        coll.objects.link(portal)
        portal.parent = root
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.95, depth=0.12)
        step = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        step.data.materials.append(mat_stone)
        add_outline(step, 0.02, self.mat_outline)
        step.parent = root
        for o in list(root.children) + [root]:
            for cl in list(o.users_collection):
                cl.objects.unlink(o)
            self.ink.objects.link(o)

    def build_orbs(self, coll):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1)
        src = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        sphere = src.data
        bpy.data.objects.remove(src)
        soft = [(0.0, 1.0), (0.45, 0.55), (0.8, 0.0)]
        self.orbs = []
        for k, col in enumerate(((0.8, 1.0, 0.97), (1.0, 0.85, 0.95))):
            core_me = sphere.copy()
            core_me.materials.append(glow_material(f"OrbCore{k}", (1, 1, 1), 4.0))
            core = bpy.data.objects.new(f"orb{k}", core_me)
            coll.objects.link(core)
            halo_me = sphere.copy()
            halo_me.materials.append(soft_material(f"OrbHalo{k}", col, 1.1, soft))
            halo = bpy.data.objects.new(f"orbhalo{k}", halo_me)
            coll.objects.link(halo)
            trail_me = sphere.copy()
            trail_me.materials.append(soft_material(f"Trail{k}", col, 0.9, soft))
            trail = []
            for j in range(18):
                g = bpy.data.objects.new(f"trail{k}_{j}", trail_me)
                coll.objects.link(g)
                trail.append(g)
            self.orbs.append((core, halo, trail))

    def build_free_petals(self, coll):
        rnd = self.rnd
        P = 240
        self.fp = np.array([[rnd.random(), rnd.random(), rnd.random(), rnd.uniform(0.06, 0.13)] for _ in range(P)])
        colors = rnd.choices(range(len(PETAL_COLORS)), weights=PETAL_WEIGHTS, k=P)
        v, f = petal_geometry(width=0.55, cup=0.18, curl=0.1, nu=6, nv=4)
        self.free_mesh = InstancedMesh("free_petals", v, f, colors, self.petal_mats, coll)

    # ------------------------------------------------------------ camera / light

    def look(self, loc, target, up=Vector((0, 0, 1)), roll=0.0, lens=35):
        loc, target = Vector(loc), Vector(target)
        fwd = (target - loc).normalized()
        right = fwd.cross(up)
        if right.length < 1e-4:
            right = fwd.cross(Vector((1, 0, 0)))
        right.normalize()
        cam_up = right.cross(fwd)
        if roll:
            c, s = math.cos(roll), math.sin(roll)
            right, cam_up = right * c + cam_up * s, cam_up * c - right * s
        m = Matrix((right, cam_up, -fwd)).transposed()
        self.cam.location = loc
        self.cam.rotation_quaternion = m.to_quaternion()
        self.cam.data.lens = lens

    def set_light_from_camera(self, side=-0.55, up=0.65, back=0.5):
        m = self.cam.rotation_quaternion.to_matrix()
        right, upv, fwd = m.col[0], m.col[1], -m.col[2]
        light = (right * side + upv * up - fwd * back).normalized()
        node = self.params.nodes["light"]
        for i in range(3):
            node.inputs[i].default_value = light[i]

    def set_glow(self, v):
        self.params.nodes["glow"].outputs[0].default_value = v

    # ------------------------------------------------------------ per frame

    def frame(self, t):
        kick = self.feature(self.kick, t)
        self.set_glow(0.0)
        portal = self.mat_portal.node_tree.nodes["emit"].inputs["Strength"]
        portal.default_value = 1.5
        orbs_visible = False
        n = self.p0
        tx, ty, _ = basis_from(n)
        ang_to_p0 = np.arccos(np.clip(self.flower_dir @ np.array(tuple(n)), -1, 1))

        if t < T_LINE1:  # A：贴地，含苞
            p = (t - 217.0) / (T_LINE1 - 217.0)
            loc = n * (R + 0.26) + tx * lerp(-1.0, -0.85, p)
            target = n * (R + 0.3) + tx * 0.8
            self.look(loc, target, up=n, roll=math.radians(-3), lens=26)
            bloom = 0.06 + 0.05 * np.sin(t * 3 + self.flower_phase)
            petal_mode = "calm"
        elif t < T_LINE2:  # B：拔地而起，花朵一圈圈绽放
            p = (t - T_LINE1) / (T_LINE2 - T_LINE1)
            rise = ease_in_out(p)
            loc = n * lerp(R + 0.3, R + 8.0, rise) + tx * lerp(-0.85, -2.2, rise)
            target = n * lerp(R + 0.9, R, ease_out(p * 1.6)) + tx * lerp(0.8, 0.0, rise)
            up = (n * (1 - rise) + tx * rise).normalized()
            self.look(loc, target, up=up, roll=math.radians(lerp(-3, 18, rise)), lens=lerp(24, 30, rise))
            wave = (t - T_LINE1) * 0.55
            bloom = np.array([ease_out((wave - a) / 0.25) for a in ang_to_p0]) + 0.06
            petal_mode = "burst"
        elif t < T_LINE3:  # C：环绕星球，两颗光相会
            p = (t - T_LINE2) / (T_LINE3 - T_LINE2)
            ang = math.radians(lerp(-40, 70, ease_in_out(p)))
            dist = lerp(12.0, 10.5, p)
            loc = Vector((dist * math.cos(ang), dist * math.sin(ang), lerp(3.2, 1.6, p)))
            self.look(loc, Vector((0, 0, 0.3)), roll=math.radians(lerp(-8, 6, p)), lens=33)
            burst = t - T_MEET
            self.set_glow(ease_out(burst / 0.35) * math.exp(-burst * 1.3) * 2.0 if burst > 0 else 0.0)
            bloom = np.ones(self.F)
            orbs_visible = True
            petal_mode = "orbit"
        elif t < T_LINE4:  # D：推向未知之门
            p = (t - T_LINE3) / (T_THROUGH - T_LINE3)
            fwd, up = self.door_forward, self.door_up
            c = self.door_center
            k = ease_in_out(clamp(p))
            loc = (c + fwd * 8.0 + up * 2.6).lerp(c + fwd * 0.35, k)
            target = (c + up * 0.2).lerp(c - fwd * 1.0, k)
            self.look(loc, target, up=up, roll=math.radians(lerp(5, 0, k)), lens=lerp(38, 24, k))
            portal.default_value = lerp(1.5, 14.0, clamp(p) ** 2.2)
            bloom = np.ones(self.F)
            petal_mode = "door"
        else:  # E：远景，巨花盛开 + 花瓣环
            p = (t - T_LINE4) / 4.7
            ang = math.radians(lerp(206, 226, p))
            dist = lerp(13.0, 15.5, ease_out(p))
            loc = Vector((dist * math.cos(ang), dist * math.sin(ang), lerp(-2.2, -1.4, p)))
            self.look(loc, Vector((0, 0, 0.3)), roll=math.radians(-9), lens=34)
            delay = 0.15 + (self.flower_phase % 1) * 0.9
            bloom = np.where(self.flower_giant, np.array([ease_out((t - T_LINE4 - d) / 1.5) for d in delay]) * 1.05, 1.0)
            self.set_glow(0.2)
            petal_mode = "ring"

        self.set_light_from_camera()
        self.update_flowers(bloom, t, 0.05 + 0.08 * kick)
        self.update_orbs(t, orbs_visible)
        self.update_free_petals(t, petal_mode)

    def orb_pos(self, k, tt):
        p = clamp((tt - T_LINE2) / (T_MEET - T_LINE2))
        ang = math.radians(lerp(-120, 25, p) + (0 if k == 0 else 150) * (1 - ease_out(p)))
        r = lerp(7.2, 5.0, p)
        z = lerp(2.6 if k == 0 else -2.2, 1.3, ease_out(p))
        base = Vector((r * math.cos(ang), r * math.sin(ang), z))
        if tt > T_MEET:
            q = tt - T_MEET
            a = q * 5 + k * math.pi
            base = base + Vector((0, 0, q * 1.4)) + Vector((math.cos(a), math.sin(a), 0)) * 0.35 * min(q, 1)
        return base

    def update_orbs(self, t, visible):
        for k, (core, halo, trail) in enumerate(self.orbs):
            for o in [core, halo] + trail:
                o.hide_render = not visible
            if not visible:
                continue
            pos = self.orb_pos(k, t)
            core.location = halo.location = pos
            core.scale = (0.05,) * 3
            halo.scale = (0.22,) * 3
            for j, g in enumerate(trail):
                g.location = self.orb_pos(k, t - (j + 1) * 0.03)
                s = 0.12 * (1 - j / len(trail)) ** 1.3
                g.scale = (s, s, s)

    def update_free_petals(self, t, mode):
        a, b, c, size = self.fp.T
        spin = t * (1.5 + 2 * a) + b * 6.28
        if mode in ("calm", "burst"):
            n = self.p0
            tx, ty, _ = (np.array(tuple(v)) for v in basis_from(n))
            nn = np.array(tuple(n))
            if mode == "calm":
                h = R + 0.15 + 0.9 * c + 0.05 * np.sin(t + b * 9)
                pos = nn[None] * h[:, None] + tx[None] * (-0.4 + 2.6 * a)[:, None] + ty[None] * (-1.3 + 2.6 * b)[:, None]
                s = size * 0.55 * (a < 0.45)
            else:
                q = np.clip((t - T_LINE1 - c * 0.8) / 3.4, 0, 1)
                h = R + 0.1 + (1 - (1 - q) ** 3) * (3 + 7 * a)
                ang = b * 6.28 + q * (3 + 3 * c)
                rad = 0.3 + q * (1.5 + 3 * c)
                pos = nn[None] * h[:, None] + (tx[None] * np.cos(ang)[:, None] + ty[None] * np.sin(ang)[:, None]) * rad[:, None]
                s = size * np.where(q > 0, 1.2, 0.0)
        elif mode == "orbit":
            ang = b * 6.28 + t * (0.25 + 0.2 * a)
            r = R * (1.25 + 0.9 * c)
            pos = np.stack([r * np.cos(ang), r * np.sin(ang), (a - 0.5) * 6], axis=1)
            s = size * 1.4
        elif mode == "door":
            fwd, up, x = (np.array(tuple(v)) for v in (self.door_forward, self.door_up, self.door_x))
            q = (t * 0.6 + a) % 1
            c0 = np.array(tuple(self.door_center))
            pos = c0[None] + up[None] * ((c - 0.5) * 1.6)[:, None] + fwd[None] * (-1.0 + 7.0 * q)[:, None] + x[None] * ((b - 0.5) * 3.0)[:, None]
            s = size * 1.0
        else:  # ring
            ang = b * 6.28 + t * 0.35
            r = R * (1.5 + 0.45 * c)
            tilt = math.radians(22)
            x, y, z = r * np.cos(ang), r * np.sin(ang), (a - 0.5) * 0.35
            pos = np.stack([x, y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)], axis=1)
            s = size * 1.8
        rot = euler_xyz(spin, spin * 0.7 + a, spin * 0.4)
        self.free_mesh.update(rot, np.asarray(s, dtype=np.float64) * np.ones(len(a)), pos)

    def render(self, t, path):
        self.frame(t)
        self.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("features")
    ap.add_argument("outdir")
    ap.add_argument("--start", type=float, default=217.0)
    ap.add_argument("--end", type=float, default=237.5)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--still", default=None)
    ap.add_argument("--scale", type=int, default=100)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--part", default="0/1", help="i/n：只渲染第 i 份（并行用）")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    pv = PV(args.features, args.fps)
    pv.scene.render.resolution_percentage = args.scale
    if args.samples:
        pv.scene.cycles.samples = args.samples
    if args.threads:
        pv.scene.render.threads_mode = "FIXED"
        pv.scene.render.threads = args.threads
    if args.still:
        for s in args.still.split(","):
            t0 = time.time()
            path = os.path.join(os.path.abspath(args.outdir), f"still_{float(s):07.2f}.png")
            pv.render(float(s), path)
            print(path, f"{time.time() - t0:.1f}s", flush=True)
        return
    a, b = round(args.start * args.fps), round(args.end * args.fps)
    i, n = map(int, args.part.split("/"))
    frames = list(range(a, b))[i::n]
    t0 = time.time()
    for k, f in enumerate(frames):
        path = os.path.join(os.path.abspath(args.outdir), f"{f:06d}.png")
        if os.path.exists(path):
            continue
        pv.render(f / args.fps, path)
        if k % 12 == 0:
            print(f"[{i}/{n}] {k + 1}/{len(frames)} 帧，平均 {(time.time() - t0) / (k + 1):.2f} 秒/帧", flush=True)


if __name__ == "__main__":
    main()
