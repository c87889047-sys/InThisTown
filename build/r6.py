"""Roblox-style R6 rig + simple Roblox-style set pieces, built in Blender (bpy).

R6 proportions (studs = Blender units), exactly as the classic rig:
  Torso 2 x 2 x 1, Left/Right Arm 1 x 2 x 1, Left/Right Leg 1 x 2 x 1,
  Head = classic "Head" mesh (rounded cylinder ~1.2 x 1.2 x 1.2) on top of the torso.
Character faces -Y. Feet at z=0.
"""
import math
import os
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACES = os.path.join(ROOT, "assets", "faces")

_mat_cache = {}


def srgb(c):
    """sRGB 0-1 -> linear."""
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c[:3])


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _mat_cache.clear()


def mat(color, rough=0.55, name=None, emission=0.0, metallic=0.0):
    key = (tuple(round(c, 3) for c in color), rough, emission, metallic)
    if key in _mat_cache:
        return _mat_cache[key]
    m = bpy.data.materials.new(name or "m")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    lin = srgb(color)
    b.inputs["Base Color"].default_value = (*lin, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emission:
        b.inputs["Emission Color"].default_value = (*lin, 1)
        b.inputs["Emission Strength"].default_value = emission
    _mat_cache[key] = m
    return m


def _finish(obj, material, bevel=0.04, parent=None):
    if material is not None:
        obj.data.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("bev", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    for p in obj.data.polygons:
        p.use_smooth = False
    if parent is not None:
        obj.parent = parent
    return obj


def box(size, loc, material, bevel=0.04, rot=(0, 0, 0), parent=None, name="part"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(o, material, bevel, parent)


def cyl(r, depth, loc, material, rot=(0, 0, 0), verts=32, bevel=0.03, parent=None, r2=None, name="cyl"):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=depth, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.object
    o.name = name
    _finish(o, material, bevel, parent)
    for p in o.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return o


def sphere(r, loc, material, scale=(1, 1, 1), parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=24, ring_count=12)
    o = bpy.context.object
    o.scale = scale
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = True
    if parent:
        o.parent = parent
    return o


def text(body, loc, size, material, rot=(math.pi / 2, 0, 0), extrude=0.02, align="CENTER", font=None):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    o = bpy.context.object
    o.data.body = body
    o.data.size = size
    o.data.extrude = extrude
    o.data.align_x = align
    o.data.align_y = "CENTER"
    if font:
        o.data.font = bpy.data.fonts.load(font, check_existing=True)
    o.data.materials.append(material)
    return o


# ---------------------------------------------------------------- head + face
def face_material(skin, face):
    """Skin material with a Roblox face decal projected onto the front (-Y) of the head."""
    m = bpy.data.materials.new("head_" + face)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.5
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    # u = x/1.12 + .5 ; v = z/1.12 + .5   (face covers the front of the head)
    u = N.new("ShaderNodeMath"); u.operation = "MULTIPLY_ADD"
    u.inputs[1].default_value = 1 / 1.0; u.inputs[2].default_value = 0.5
    v = N.new("ShaderNodeMath"); v.operation = "MULTIPLY_ADD"
    v.inputs[1].default_value = 1 / 1.0; v.inputs[2].default_value = 0.5
    L.new(sep.outputs[0], u.inputs[0]); L.new(sep.outputs[2], v.inputs[0])
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(u.outputs[0], comb.inputs[0]); L.new(v.outputs[0], comb.inputs[1])
    img = N.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(FACES, face + ".png"), check_existing=True)
    img.extension = "CLIP"
    img.interpolation = "Cubic"
    L.new(comb.outputs[0], img.inputs[0])
    front = N.new("ShaderNodeMath"); front.operation = "LESS_THAN"
    front.inputs[1].default_value = -0.05
    L.new(sep.outputs[1], front.inputs[0])
    a = N.new("ShaderNodeMath"); a.operation = "MULTIPLY"
    L.new(img.outputs["Alpha"], a.inputs[0]); L.new(front.outputs[0], a.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*srgb(skin), 1)
    L.new(a.outputs[0], mix.inputs[0])
    L.new(img.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def head_mesh(material, parent):
    """Classic R6 head: cylinder (vertical axis) with rounded top/bottom edges."""
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=1.2, vertices=48, location=(0, 0, 0))
    o = bpy.context.object
    o.name = "Head"
    bev = o.modifiers.new("bev", "BEVEL")
    bev.width = 0.2
    bev.segments = 6
    bev.limit_method = "ANGLE"
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = True
    o.parent = parent
    return o


# ---------------------------------------------------------------- R6 character
class R6:
    def __init__(self, name, skin, shirt, pants, face="neutral", hair=None, hair_color=(0.3, 0.15, 0.05),
                 sleeves=True, hat=None, torso_tex=None, loc=(0, 0, 0), rot=0.0, pose=None, shoes=None,
                 head_turn=0.0, head_tilt=0.0, scale=1.0):
        self.name = name
        root = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(root)
        root.location = loc
        root.rotation_euler = (0, 0, rot)
        root.scale = (scale,) * 3
        self.root = root
        pose = pose or {}
        skin_m = mat(skin, 0.5)
        shirt_m = mat(shirt, 0.6)
        pants_m = mat(pants, 0.6)
        # torso (optionally with a printed front texture, e.g. suit)
        tm = shirt_m
        if torso_tex:
            tm = torso_texture_material(torso_tex, shirt)
        box((2, 1, 2), (0, 0, 3), tm, parent=root, name="Torso")
        # legs
        for side, sx in (("L", -0.5), ("R", 0.5)):
            piv = self._pivot(f"Hip{side}", (sx, 0, 2), pose.get(f"leg{side}", 0), pose.get(f"leg{side}_side", 0))
            box((1, 1, 2), (0, 0, -1), pants_m, parent=piv, name=f"Leg{side}")
            if shoes:
                box((1.02, 1.02, 0.35), (0, 0, -1.82), mat(shoes), parent=piv, name="shoe")
        # arms
        for side, sx in (("L", -1.5), ("R", 1.5)):
            piv = self._pivot(f"Shoulder{side}", (sx, 0, 3.5), pose.get(f"arm{side}", 0),
                              pose.get(f"arm{side}_side", 0) * (1 if side == "R" else -1))
            arm_m = shirt_m if sleeves else skin_m
            box((1, 1, 2), (0, 0, -1), arm_m, parent=piv, name=f"Arm{side}")
            if sleeves == "short":
                box((1.01, 1.01, 1.0), (0, 0, -1.5), skin_m, parent=piv, name="forearm")
            self.__dict__["hand" + side] = piv
        # head
        hp = self._pivot("Neck", (0, 0, 4.0), head_tilt, 0, head_turn)
        self.head_pivot = hp
        hm = face_material(skin, face)
        self.head = head_mesh(hm, hp)
        self.head.location = (0, 0, 0.6)
        if hair:
            HAIR[hair](hp, mat(hair_color, 0.7))
        if hat:
            HATS[hat](hp)

    def _pivot(self, name, loc, rx=0.0, ry=0.0, rz=0.0):
        e = bpy.data.objects.new(f"{self.name}_{name}", None)
        bpy.context.collection.objects.link(e)
        e.parent = self.root
        e.location = loc
        e.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        return e

    def hold(self, side, obj_builder):
        """Attach a prop to the end of an arm (hand at local z=-2)."""
        piv = self.__dict__["hand" + side]
        return obj_builder(piv)


def torso_texture_material(kind, base):
    m = bpy.data.materials.new("torso_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.55
    tc = N.new("ShaderNodeTexCoord")
    img = N.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(ROOT, "assets", "textures", kind + ".png"), check_existing=True)
    img.extension = "EXTEND"
    mp = N.new("ShaderNodeMapping")
    # object coords x in [-1,1], z in [-1,1] (torso is centred on its own origin after apply) -> uv
    mp.inputs["Location"].default_value = (0.5, 0.5, 0)
    mp.inputs["Scale"].default_value = (0.5, 0.5, 1)
    sep = N.new("ShaderNodeSeparateXYZ")
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    L.new(sep.outputs[0], comb.inputs[0])
    L.new(sep.outputs[2], comb.inputs[1])
    L.new(comb.outputs[0], mp.inputs[0])
    L.new(mp.outputs[0], img.inputs[0])
    front = N.new("ShaderNodeMath"); front.operation = "LESS_THAN"; front.inputs[1].default_value = -0.45
    L.new(sep.outputs[1], front.inputs[0])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*srgb(base), 1)
    L.new(front.outputs[0], mix.inputs[0])
    L.new(img.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    return m


# ---------------------------------------------------------------- hair / hats
def hair_spiky(p, m):
    box((1.3, 1.3, 0.45), (0, 0.05, 1.24), m, bevel=0.15, parent=p)
    box((1.32, 0.5, 1.0), (0, 0.45, 0.8), m, bevel=0.15, parent=p)
    for (x, y, rx, ry, h) in [(-0.4, -0.3, -25, -20, 0.6), (0, -0.4, -35, 0, 0.7), (0.4, -0.3, -25, 20, 0.6),
                              (-0.3, 0.2, 10, -25, 0.6), (0.3, 0.2, 10, 25, 0.6), (0, 0.1, 0, 0, 0.75),
                              (-0.55, -0.1, 0, -40, 0.45), (0.55, -0.1, 0, 40, 0.45)]:
        cyl(0.28, h, (x, y, 1.35 + h * 0.3), m, rot=(math.radians(rx), math.radians(ry), 0), verts=4, r2=0.0,
            parent=p, bevel=0)
    # side bits over the ears
    box((0.15, 0.7, 0.55), (-0.62, 0.1, 0.85), m, bevel=0.05, parent=p)
    box((0.15, 0.7, 0.55), (0.62, 0.1, 0.85), m, bevel=0.05, parent=p)


def hair_short(p, m):
    box((1.28, 1.28, 0.42), (0, 0.04, 1.26), m, bevel=0.17, parent=p)
    box((1.3, 0.55, 0.9), (0, 0.4, 0.85), m, bevel=0.15, parent=p)


def hair_long(p, m):
    box((1.34, 1.34, 0.45), (0, 0.04, 1.25), m, bevel=0.18, parent=p)
    box((1.4, 0.6, 1.9), (0, 0.42, 0.35), m, bevel=0.2, parent=p)
    box((0.25, 0.9, 1.6), (-0.66, 0.0, 0.45), m, bevel=0.1, parent=p)
    box((0.25, 0.9, 1.6), (0.66, 0.0, 0.45), m, bevel=0.1, parent=p)
    box((1.0, 0.25, 0.25), (-0.12, -0.57, 1.1), m, bevel=0.1, parent=p, rot=(0, math.radians(10), 0))


def hair_pigtails(p, m):
    hair_short(p, m)
    sphere(0.32, (-0.8, 0.2, 0.9), m, parent=p)
    sphere(0.32, (0.8, 0.2, 0.9), m, parent=p)


def hair_bald(p, m):
    pass


HAIR = {"spiky": hair_spiky, "short": hair_short, "long": hair_long, "pigtails": hair_pigtails, "bald": hair_bald}


def hat_top(p):
    black = mat((0.04, 0.04, 0.05), 0.35)
    cyl(1.05, 0.08, (0, 0, 1.22), black, parent=p, verts=48)
    cyl(0.72, 1.5, (0, 0, 1.98), black, parent=p, verts=48)
    cyl(0.735, 0.22, (0, 0, 1.4), mat((0.55, 0.05, 0.08), 0.5), parent=p, verts=48)


def hat_police(p):
    navy = mat((0.07, 0.1, 0.25), 0.5)
    cyl(0.7, 0.45, (0, 0.05, 1.55), navy, parent=p, verts=40, r2=0.8)
    cyl(0.64, 0.16, (0, 0.03, 1.3), mat((0.05, 0.05, 0.06), 0.3), parent=p, verts=40)
    box((1.0, 0.45, 0.06), (0, -0.62, 1.26), mat((0.03, 0.03, 0.03), 0.25), parent=p,
        rot=(math.radians(-8), 0, 0), bevel=0.02)
    box((0.22, 0.05, 0.25), (0, -0.74, 1.57), mat((0.95, 0.75, 0.2), 0.25, metallic=0.8), parent=p, bevel=0.01)


HATS = {"top": hat_top, "police": hat_police}


# ---------------------------------------------------------------- props
def prop_paper(p, color=(0.97, 0.97, 0.95)):
    return box((0.9, 0.05, 1.1), (0, -0.6, -2.2), mat(color, 0.8), parent=p, bevel=0.01)


def prop_burger(p):
    pass


def pigeon(loc, rot=0, parent=None, scale=1.0):
    g = mat((0.55, 0.57, 0.62), 0.6)
    root = bpy.data.objects.new("pigeon", None)
    bpy.context.collection.objects.link(root)
    root.location = loc
    root.rotation_euler = (0, 0, rot)
    root.scale = (scale,) * 3
    if parent:
        root.parent = parent
    box((0.6, 0.9, 0.55), (0, 0.1, 0.3), g, parent=root, bevel=0.12)
    box((0.45, 0.45, 0.45), (0, -0.4, 0.7), mat((0.35, 0.38, 0.45), 0.5), parent=root, bevel=0.1)
    box((0.15, 0.25, 0.12), (0, -0.72, 0.65), mat((0.95, 0.6, 0.15), 0.5), parent=root, bevel=0.02)
    for x in (-0.16, 0.16):
        box((0.1, 0.05, 0.1), (x, -0.63, 0.8), mat((0.02, 0.02, 0.02), 0.2), parent=root, bevel=0.0)
        box((0.08, 0.08, 0.3), (x, 0.1, -0.05), mat((0.95, 0.5, 0.4)), parent=root, bevel=0.0)
    box((0.1, 0.8, 0.45), (-0.33, 0.15, 0.32), mat((0.45, 0.47, 0.52), 0.6), parent=root, bevel=0.05)
    box((0.1, 0.8, 0.45), (0.33, 0.15, 0.32), mat((0.45, 0.47, 0.52), 0.6), parent=root, bevel=0.05)
    box((0.4, 0.5, 0.12), (0, 0.7, 0.4), g, parent=root, bevel=0.03, rot=(math.radians(20), 0, 0))
    return root


def poop(loc, parent=None, s=0.35):
    br = mat((0.38, 0.2, 0.08), 0.35)
    objs = []
    for i, (r, z) in enumerate([(1.0, 0), (0.75, 0.5), (0.48, 0.9)]):
        bpy.ops.mesh.primitive_torus_add(major_radius=r * s, minor_radius=0.32 * s, location=(loc[0], loc[1], loc[2] + z * s))
        o = bpy.context.object
        o.data.materials.append(br)
        for pp in o.data.polygons:
            pp.use_smooth = True
        if parent:
            o.parent = parent
        objs.append(o)
    cyl(0.2 * s, 0.5 * s, (loc[0], loc[1], loc[2] + 1.25 * s), br, r2=0.0, parent=parent)
    return objs


# ---------------------------------------------------------------- world / sets
def setup_render(res=(1080, 1920), samples=32):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False


def sky_and_sun(sun_rot=(math.radians(50), math.radians(10), math.radians(30)), strength=3.2, sky=(0.55, 0.75, 1.0),
                sky_strength=0.9):
    w = bpy.data.worlds.new("w")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*srgb(sky), 1)
    bg.inputs[1].default_value = sky_strength
    bpy.ops.object.light_add(type="SUN", rotation=sun_rot)
    s = bpy.context.object
    s.data.energy = strength
    s.data.angle = math.radians(4)
    return s


def camera(loc, target, lens=35):
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.object
    c.data.lens = lens
    c.data.sensor_fit = "VERTICAL"
    c.data.sensor_height = 24 * 16 / 9 * 9 / 16  # keep a 24mm vertical-ish feel
    d = Vector(target) - Vector(loc)
    c.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = c
    c.data.clip_end = 2000
    return c


def ground(color=(0.36, 0.6, 0.25), size=600):
    m = bpy.data.materials.new("grass")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.9
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 8
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*srgb(tuple(c * 0.8 for c in color)), 1)
    ramp.color_ramp.elements[1].color = (*srgb(tuple(min(1, c * 1.15) for c in color)), 1)
    L.new(noise.outputs["Fac"], ramp.inputs[0])
    L.new(ramp.outputs[0], b.inputs["Base Color"])
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    bpy.context.object.data.materials.append(m)


def road(y=0.0, width=14, length=400):
    box((length, width, 0.1), (0, y, 0.05), mat((0.22, 0.22, 0.24), 0.85), bevel=0)
    for x in range(-length // 2, length // 2, 8):
        box((4, 0.35, 0.02), (x, y, 0.11), mat((0.95, 0.8, 0.2), 0.6), bevel=0)
    for sy in (y - width / 2 - 3, y + width / 2 + 3):
        box((length, 6, 0.4), (0, sy, 0.2), mat((0.72, 0.72, 0.7), 0.8), bevel=0.02)


def tree(loc, s=1.0):
    x, y, z = loc
    cyl(0.6 * s, 4 * s, (x, y, z + 2 * s), mat((0.42, 0.26, 0.13), 0.9), verts=8)
    g = mat((0.2, 0.52, 0.22), 0.8)
    for i, (r, h) in enumerate([(3.6, 4), (2.8, 3.6), (1.9, 3.2)]):
        cyl(r * s, h * s, (x, y, z + (4 + i * 2.3) * s), g, r2=0.15 * s, verts=8, bevel=0)


def house(loc, rot=0, wall=(0.93, 0.8, 0.5), roof=(0.7, 0.13, 0.1), door=(0.8, 0.08, 0.08), w=16, d=12, h=10):
    root = bpy.data.objects.new("house", None)
    bpy.context.collection.objects.link(root)
    root.location = loc
    root.rotation_euler = (0, 0, rot)
    wm = mat(wall, 0.85)
    box((w, d, h), (0, 0, h / 2), wm, parent=root, bevel=0.05)
    # roof: two slanted slabs
    import math as _m
    ang = _m.radians(28)
    half = d / 2 + 1
    L = half / _m.cos(ang)
    for s in (-1, 1):
        box((w + 2, L, 0.6), (0, s * half / 2, h + _m.tan(ang) * half / 2), mat(roof, 0.7), parent=root,
            rot=(s * -ang, 0, 0), bevel=0.05)
    # gable fill
    bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=1, depth=w, location=(0, 0, 0))
    g = bpy.context.object
    g.scale = (_m.tan(ang) * half * 1.0, half * 1.0, 1)
    g.rotation_euler = (0, _m.radians(90), 0)
    g.location = (0, 0, h + 0.0)
    g.data.materials.append(wm)
    g.parent = root
    g.scale = (1, half, _m.tan(ang) * half)
    g.rotation_euler = (0, _m.radians(90), _m.radians(90))
    g.rotation_mode = "XYZ"
    # windows + door on front (-Y)
    glass = mat((0.45, 0.7, 0.95), 0.1)
    white = mat((0.97, 0.97, 0.97), 0.6)
    for wx in (-w / 2 + 3.5, w / 2 - 3.5):
        box((3.4, 0.3, 3.4), (wx, -d / 2 - 0.05, h * 0.55), white, parent=root, bevel=0.03)
        box((2.8, 0.35, 2.8), (wx, -d / 2 - 0.08, h * 0.55), glass, parent=root, bevel=0)
        box((0.25, 0.4, 2.8), (wx, -d / 2 - 0.1, h * 0.55), white, parent=root, bevel=0)
        box((2.8, 0.4, 0.25), (wx, -d / 2 - 0.1, h * 0.55), white, parent=root, bevel=0)
        for sx in (-1, 1):
            box((0.9, 0.3, 3.6), (wx + sx * 2.3, -d / 2 - 0.05, h * 0.55), mat((0.3, 0.5, 0.75), 0.6), parent=root)
    box((3.2, 0.3, 6.2), (0, -d / 2 - 0.05, 3.1), white, parent=root)
    box((2.6, 0.4, 5.8), (0, -d / 2 - 0.1, 2.9), mat(door, 0.5), parent=root)
    sphere(0.18, (0.9, -d / 2 - 0.35, 2.9), mat((0.95, 0.8, 0.3), 0.3, metallic=0.8), parent=root)
    box((5, 2.5, 0.4), (0, -d / 2 - 1.2, 0.2), mat((0.75, 0.75, 0.72)), parent=root)
    return root


def fence(x0, x1, y, h=2.2):
    white = mat((0.97, 0.97, 0.97), 0.6)
    box((x1 - x0, 0.25, 0.3), ((x0 + x1) / 2, y, h * 0.7), white, bevel=0.02)
    box((x1 - x0, 0.25, 0.3), ((x0 + x1) / 2, y, h * 0.3), white, bevel=0.02)
    x = x0
    while x <= x1:
        box((0.5, 0.3, h), (x, y - 0.05, h / 2), white, bevel=0.03)
        x += 1.2


def sign(loc, rot, lines, board=(0.97, 0.97, 0.95), fg=(0.8, 0.05, 0.05), w=7, h=4.5, font=None):
    root = bpy.data.objects.new("sign", None)
    bpy.context.collection.objects.link(root)
    root.location = loc
    root.rotation_euler = (0, 0, rot)
    post = mat((0.35, 0.22, 0.1), 0.8)
    box((0.4, 0.4, 5), (-w / 2 + 0.8, 0.3, 2.5), post, parent=root)
    box((0.4, 0.4, 5), (w / 2 - 0.8, 0.3, 2.5), post, parent=root)
    box((w, 0.3, h), (0, 0, 5 + h / 2 - 1), mat(board, 0.7), parent=root)
    box((w + 0.3, 0.25, h + 0.3), (0, 0.06, 5 + h / 2 - 1), mat(fg, 0.6), parent=root)
    n = len(lines)
    for i, (t, size, col) in enumerate(lines):
        o = text(t, (0, -0.2, 5 + h / 2 - 1 + (n - 1) * 0.55 - i * 1.1), size, mat(col, 0.5), font=font)
        o.parent = root
        o.location = (0, -0.2, 5 + h / 2 - 1 + (n - 1) * 0.6 - i * 1.2)
    return root


def car(loc, rot=0, body=(0.95, 0.95, 0.97), police=True):
    root = bpy.data.objects.new("car", None)
    bpy.context.collection.objects.link(root)
    root.location = loc
    root.rotation_euler = (0, 0, rot)
    bm = mat(body, 0.35)
    black = mat((0.05, 0.05, 0.07), 0.4)
    box((5.2, 11, 2.2), (0, 0, 1.9), black if police else bm, parent=root, bevel=0.25)
    box((5.25, 5, 2.25), (0, 0, 1.92), bm, parent=root, bevel=0.25)
    box((4.6, 5.6, 1.9), (0, 0.6, 3.8), bm, parent=root, bevel=0.3)
    glass = mat((0.15, 0.2, 0.28), 0.05)
    box((4.65, 5.0, 1.4), (0, 0.6, 3.85), glass, parent=root, bevel=0.2)
    for x in (-2.4, 2.4):
        for y in (-3.4, 3.4):
            cyl(1.0, 0.8, (x, y, 1.0), mat((0.08, 0.08, 0.08), 0.8), rot=(0, math.radians(90), 0), parent=root)
            cyl(0.5, 0.85, (x, y, 1.0), mat((0.7, 0.7, 0.72), 0.3, metallic=0.7), rot=(0, math.radians(90), 0),
                parent=root)
    if police:
        box((1.5, 0.9, 0.5), (-0.8, 0.6, 5.0), mat((0.95, 0.1, 0.1), 0.3, emission=4), parent=root, bevel=0.1)
        box((1.5, 0.9, 0.5), (0.8, 0.6, 5.0), mat((0.15, 0.35, 1.0), 0.3, emission=4), parent=root, bevel=0.1)
        for side in (-1, 1):
            t = text("FROWN POLICE", (side * 2.66, 0, 2.0), 0.75, mat((0.05, 0.1, 0.4), 0.5),
                     rot=(math.pi / 2, 0, side * math.pi / 2), extrude=0.03)
            t.parent = root
            t.location = (side * 2.66, 0, 1.9)
    box((4.6, 0.3, 0.5), (0, -5.55, 1.6), mat((0.95, 0.95, 0.85), 0.3, emission=1.5), parent=root, bevel=0.1)
    return root


def room(w=30, d=24, h=14, wall=(0.93, 0.89, 0.8), floor=(0.55, 0.35, 0.2), trim=(0.25, 0.45, 0.7)):
    """Interior: back wall at +Y, side walls, floor; camera looks toward +Y."""
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    N, L = fm.node_tree.nodes, fm.node_tree.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.4
    wave = N.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 0.6
    wave.inputs["Distortion"].default_value = 3
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*srgb(tuple(c * 0.8 for c in floor)), 1)
    ramp.color_ramp.elements[1].color = (*srgb(floor), 1)
    L.new(wave.outputs["Fac"], ramp.inputs[0])
    L.new(ramp.outputs[0], b.inputs["Base Color"])
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    f = bpy.context.object
    f.scale = (w * 3, d * 3, 1)
    f.data.materials.append(fm)
    wm = mat(wall, 0.85)
    box((w, 1, h), (0, d / 2, h / 2), wm, bevel=0)
    box((1, d * 2, h), (-w / 2, 0, h / 2), wm, bevel=0)
    box((1, d * 2, h), (w / 2, 0, h / 2), wm, bevel=0)
    box((w, 0.3, 1.0), (0, d / 2 - 0.6, 0.5), mat(trim, 0.6), bevel=0)
    box((w, 1, 1), (0, 0, h + 0.5), mat((0.95, 0.95, 0.95), 0.9), bevel=0)
    # ceiling (big) for bounce light
    box((w * 2, d * 3, 0.5), (0, 0, h + 0.25), mat((0.95, 0.95, 0.95), 0.9), bevel=0)
    bpy.ops.object.light_add(type="AREA", location=(0, -2, h - 0.5))
    a = bpy.context.object
    a.data.energy = 9000
    a.data.size = 12
    bpy.ops.object.light_add(type="AREA", location=(0, -30, 9), rotation=(math.radians(80), 0, 0))
    a2 = bpy.context.object
    a2.data.energy = 14000
    a2.data.size = 20
    return wm


def window(loc, w=7, h=6, rot=0):
    root = bpy.data.objects.new("win", None)
    bpy.context.collection.objects.link(root)
    root.location = loc
    root.rotation_euler = (0, 0, rot)
    white = mat((0.97, 0.97, 0.97), 0.6)
    box((w + 0.8, 0.6, h + 0.8), (0, 0, 0), white, parent=root)
    box((w, 0.7, h), (0, 0, 0), mat((0.6, 0.82, 1.0), 0.1, emission=1.2), parent=root, bevel=0)
    box((0.3, 0.8, h), (0, 0, 0), white, parent=root, bevel=0)
    box((w, 0.8, 0.3), (0, 0, 0), white, parent=root, bevel=0)
    return root
