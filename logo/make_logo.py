import bpy, bmesh, math, os, sys
from mathutils import Vector

OUT = os.environ.get("LOGO_OUT", os.path.dirname(os.path.abspath(__file__)))
ZSHIFT = -0.12

def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    lin = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]
    return (lin[0], lin[1], lin[2], 1.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def new_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob

def principled(name, color, rough=0.4, emit=None, emit_strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    for k in ("Coat Weight", "Clearcoat"):
        if k in bsdf.inputs: bsdf.inputs[k].default_value = coat; break
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = emit
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    return m

def gradient_material(name, top, bottom):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.5; mr.inputs["From Max"].default_value = 1.5
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = bottom
    ramp.color_ramp.elements[1].color = top
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.30
    bsdf.inputs["Roughness"].default_value = 0.85
    return m

def slab(name, radius, half=1.5, y=0.62):
    bm = bmesh.new()
    pts = []
    if radius <= 0:
        pts = [(-half, -half), (half, -half), (half, half), (-half, half)]
    else:
        corners = [(half - radius, half - radius, 0), (-half + radius, half - radius, 90),
                   (-half + radius, -half + radius, 180), (half - radius, -half + radius, 270)]
        for cx, cz, a0 in corners:
            for i in range(0, 13):
                a = math.radians(a0 + i * 90 / 12)
                pts.append((cx + radius * math.cos(a), cz + radius * math.sin(a)))
    vs = [bm.verts.new((x, 0, z)) for x, z in pts]
    bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_obj(name, bm)
    ob.location = (0, y, 0)
    sol = ob.modifiers.new("solid", "SOLIDIFY"); sol.thickness = 0.1; sol.offset = 1
    return ob

def frustum(name, bw, bd, tw, td, z0, z1, thick, bottom=True):
    bm = bmesh.new()
    b = [bm.verts.new((sx * bw / 2, sy * bd / 2, z0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    t = [bm.verts.new((sx * tw / 2, sy * td / 2, z1)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b[i], b[j], t[j], t[i]))
    if bottom:
        bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_obj(name, bm)
    sol = ob.modifiers.new("solid", "SOLIDIFY"); sol.thickness = thick; sol.offset = 1
    bev = ob.modifiers.new("bevel", "BEVEL"); bev.width = 0.035; bev.segments = 4; bev.limit_method = 'ANGLE'
    for p in ob.data.polygons: p.use_smooth = True
    return ob

# --- materials
white = principled("white", srgb("#F4F6F5"), rough=0.35, coat=0.2)
green = principled("check", srgb("#0B7A52"), rough=0.3, coat=0.3)
bgm_top, bgm_bot = srgb("#2DBB86"), srgb("#0C6B49")
bgmat = gradient_material("bg", bgm_top, bgm_bot)

# --- basket
body = frustum("body", 1.25, 0.72, 1.85, 1.02, -0.75, 0.30, 0.07)
rim = frustum("rim", 1.93, 1.10, 1.95, 1.12, 0.22, 0.36, 0.06, bottom=False)
for o in (body, rim):
    o.data.materials.append(white); o.location.z += ZSHIFT

# handle: half torus standing in XZ plane
bpy.ops.mesh.primitive_torus_add(major_radius=0.82, minor_radius=0.065, major_segments=64, minor_segments=24,
                                 rotation=(math.radians(90), 0, 0), location=(0, 0, 0.34 + ZSHIFT))
handle = bpy.context.active_object
bm = bmesh.new(); bm.from_mesh(handle.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.02], context='VERTS')
bm.to_mesh(handle.data); bm.free()
handle.scale = (1.0, 1.0, 0.82)
handle.data.materials.append(white)
for p in handle.data.polygons: p.use_smooth = True

# check mark: capsules (cylinder + 2 spheres) on the front face
from mathutils import Matrix
def capsule(a, b, y, name, r=0.088):
    ax, az = a; bx, bz = b
    dx, dz = bx - ax, bz - az
    L = math.hypot(dx, dz)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=r, radius2=r, depth=L)
    for sgn in (-1, 1):
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r,
                                  matrix=Matrix.Translation((0, 0, sgn * L / 2)))
    ob = new_obj(name, bm)
    for p in ob.data.polygons: p.use_smooth = True
    phi = math.atan2(dx, dz)
    ob.matrix_world = (Matrix.Translation(((ax + bx) / 2, y, (az + bz) / 2 + ZSHIFT))
                       @ Matrix.Rotation(math.radians(-7), 4, 'X') @ Matrix.Rotation(phi, 4, 'Y'))
    ob.data.materials.append(green)
    return ob

CY = -0.52
capsule((-0.46, -0.20), (-0.18, -0.52), CY, "check1")
capsule((-0.18, -0.52), (0.50, 0.12), CY, "check2")

# --- background slabs
rounded = slab("bg_round", 0.62); rounded.data.materials.append(bgmat)
square = slab("bg_square", 0.0); square.data.materials.append(bgmat)

# --- camera + light
cam = bpy.data.cameras.new("cam"); cam.type = 'ORTHO'; cam.ortho_scale = 3.0
co = bpy.data.objects.new("cam", cam); scene.collection.objects.link(co)
co.location = (0, -9, 0); co.rotation_euler = (math.radians(90), 0, 0); scene.camera = co

sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 1.5; sun.angle = math.radians(18)
so = bpy.data.objects.new("sun", sun); scene.collection.objects.link(so)
so.rotation_euler = (math.radians(55), math.radians(10), math.radians(-28))
fill = bpy.data.lights.new("fill", "AREA"); fill.energy = 80; fill.size = 5
fo = bpy.data.objects.new("fill", fill); scene.collection.objects.link(fo)
fo.location = (3.5, -5, 1.5); fo.rotation_euler = (math.radians(80), 0, math.radians(35))

world = bpy.data.worlds.new("w"); world.use_nodes = True
bg = world.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.92, 1.0, 0.96, 1)
bg.inputs["Strength"].default_value = 0.35
scene.world = world

r = scene.render
r.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 96
scene.cycles.use_denoising = True
r.resolution_x = r.resolution_y = 1024; r.resolution_percentage = 100
r.film_transparent = True
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA'

def render(name, show_round):
    rounded.hide_render = not show_round
    square.hide_render = show_round
    r.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)

render("icon_rounded_1024.png", True)
render("icon_square_1024.png", False)

# --- downsized variants via Blender
def resize(src, dst, size):
    img = bpy.data.images.load(os.path.join(OUT, src))
    img.scale(size, size)
    img.filepath_raw = os.path.join(OUT, dst); img.file_format = 'PNG'; img.save()
    bpy.data.images.remove(img)

for size in (512, 192):
    resize("icon_square_1024.png", "icon-%d.png" % size, size)
resize("icon_square_1024.png", "apple-touch-icon.png", 180)
resize("icon_rounded_1024.png", "favicon-64.png", 64)
resize("icon_rounded_1024.png", "favicon-32.png", 32)
print("LOGO_DONE")
