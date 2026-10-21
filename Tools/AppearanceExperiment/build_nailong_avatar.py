#!/usr/bin/env python3
"""Build a reference-driven, editable 3D yellow mascot in isolated Blender Python.

All geometry in this file is authored for this project. The supplied reference
is a visual reference, never a flat image substituted for a 3D avatar.
"""
from pathlib import Path
import argparse
import json
import math
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Assets/Project/Resources/AvatarDemo"
EVIDENCE = ROOT / "StudyData/avatar-v2/nailong-preview"


def material(name, rgb, roughness=.42, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*rgb, 1)
    bs.inputs["Roughness"].default_value = roughness
    bs.inputs["Metallic"].default_value = metallic
    return mat


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return obj


def mesh(name, verts, faces, mat, parent):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    data.materials.append(mat)
    for poly in data.polygons:
        poly.use_smooth = True
    return obj


def ellipsoid(name, pos, radius, mat, parent, segments=32, rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = radius
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    obj.parent = parent
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def tube(name, points, radii, mat, parent, sides=12):
    # Parallel transported circular sections avoid kinks in fingers and limbs.
    points = [Vector(p) for p in points]
    verts, faces = [], []
    previous_u = None
    for i, point in enumerate(points):
        tangent = (points[min(i+1, len(points)-1)]-points[max(0, i-1)]).normalized()
        if previous_u is None:
            axis = Vector((0, 0, 1))
            if abs(tangent.dot(axis)) > .95:
                axis = Vector((0, 1, 0))
            u = tangent.cross(axis).normalized()
        else:
            u = (previous_u-tangent*previous_u.dot(tangent)).normalized()
        v = tangent.cross(u).normalized()
        previous_u = u
        for j in range(sides):
            angle = j * math.tau/sides
            verts.append(point+radii[i]*(math.cos(angle)*u+math.sin(angle)*v))
    for i in range(len(points)-1):
        for j in range(sides):
            a = i*sides+j
            b = i*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple((len(points)-1)*sides+j for j in range(sides)))
    obj = mesh(name, verts, faces, mat, parent)
    sub = obj.modifiers.new("Sculpted continuity", "SUBSURF")
    sub.levels = sub.render_levels = 2
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=sub.name)
    return obj


# (height, width radius, depth radius, depth center); one continuous pear silhouette.
PROFILE = [
    (.38,.06,.07,.045),(.44,.22,.21,.04),(.57,.33,.29,.025),
    (.74,.405,.355,.005),(.94,.43,.375,0),(1.12,.40,.35,.005),
    (1.29,.32,.285,.015),(1.44,.245,.225,.015),(1.58,.20,.19,.005),
    (1.70,.165,.16,-.005),(1.79,.11,.12,-.005),(1.82,.075,.083,-.005),
    (1.835,.038,.042,-.005),(1.84,.001,.001,-.005),
]


def profile(z):
    i = next((i for i in range(len(PROFILE)-1) if z <= PROFILE[i+1][0]), len(PROFILE)-2)
    a, b = PROFILE[i:i+2]
    t = max(0, min(1, (z-a[0])/(b[0]-a[0])))
    # Cubic Hermite interpolation gives continuous derivatives between sculpt rings.
    result = []
    for k in (1,2,3):
        prev = PROFILE[max(0,i-1)]
        nxt = PROFILE[min(len(PROFILE)-1,i+2)]
        slope_a=(b[k]-prev[k])/(b[0]-prev[0])
        slope_b=(nxt[k]-a[k])/(nxt[0]-a[0])
        result.append((2*t**3-3*t*t+1)*a[k]+(t**3-2*t*t+t)*(b[0]-a[0])*slope_a+
                      (-2*t**3+3*t*t)*b[k]+(t**3-t*t)*(b[0]-a[0])*slope_b)
    return result


def body_mesh(mat, parent):
    verts, faces=[],[]
    rows, sides=128,64
    for i in range(rows):
        z=PROFILE[0][0]+(PROFILE[-1][0]-PROFILE[0][0])*i/(rows-1)
        rx,ry,cy=profile(z)
        for j in range(sides):
            angle=math.tau*j/sides
            x,y=rx*math.cos(angle),cy+ry*math.sin(angle)
            # Slight soft muzzle integrated with the same surface, not a separate beak.
            front=max(0,-math.sin(angle))**16
            y-=.047*math.exp(-((z-1.565)/.055)**2)*front
            verts.append((x,y,z))
    for i in range(rows-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple((rows-1)*sides+j for j in range(sides)))
    return mesh("Continuous sculpted body",verts,faces,mat,parent)


def belly(mat,parent):
    verts=[(0,profile(.98)[2]-profile(.98)[1]-.004,.98)]
    rings,sides=20,64
    for i in range(1,rings+1):
        r=i/rings
        for j in range(sides):
            t=math.tau*j/sides
            x=.302*r*math.cos(t);z=.98+.355*r*math.sin(t)
            rx,ry,cy=profile(z)
            y=cy-ry*math.sqrt(max(.01,1-(x/rx)**2))-.004
            verts.append((x,y,z))
    faces=[(0,1+j,1+(j+1)%sides) for j in range(sides)]
    for i in range(rings-1):
        for j in range(sides):
            a=1+i*sides+j;b=1+i*sides+(j+1)%sides
            faces.append((a,a+sides,b+sides,b))
    return mesh("Fitted cream belly patch",verts,faces,mat,parent)


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    root=empty("Nailong")
    body=empty("Outfit_none",root)
    yellow=material("Tint_Mascot",(.95,.59,.025),.35)
    cream=material("Belly_cream",(.79,.58,.23),.49)
    toes=material("Warm_olive_extremities",(.28,.22,.055),.43)
    dark=material("Eye_black",(.008,.012,.006),.16)
    iris=material("Eye_green",(.17,.39,.075),.22)
    white=material("Eye_catchlight",(.99,.99,.94),.12)
    frame=material("Metal_glasses",(.025,.034,.041),.25,.45)
    cap=material("Cap_navy",(.018,.033,.073),.48)
    body_mesh(yellow,body);belly(cream,body)
    for sign in (-1,1):
        # Plantigrade bent legs, broad feet and three individually shaped toes.
        tube("Hind leg",[(sign*.20,.02,.57),(sign*.245,.015,.39),(sign*.235,-.025,.21),(sign*.225,-.08,.10)],
             [.14,.125,.09,.065],yellow,body,16)
        ellipsoid("Foot pad",(sign*.225,-.12,.075),(.12,.17,.07),toes,body)
        for toe in range(3):
            x=sign*.225+(toe-1)*.073
            tube("Rounded toe",[(x,-.16,.07),(x,-.225,.057),(x,-.274+abs(toe-1)*.025,.052)],
                 [.045,.039,.024],toes,body,12)
        # Forearms fold naturally around the belly, as in the supplied reference.
        tube("Soft shoulder to wrist",[(sign*.30,-.015,1.32),(sign*.405,-.075,1.18),
             (sign*.405,-.23,1.065),(sign*.285,-.345,1.0)],[.105,.12,.106,.073],yellow,body,16)
        ellipsoid("Palm",(sign*.278,-.351,.98),(.083,.049,.102),toes,body)
        for finger in range(3):
            z=1.04-finger*.06
            tube("Belly hugging finger",[(sign*.29,-.367,z),(sign*.235,-.399,z-.012),
                 (sign*.192,-.395,z-.02)],[.029,.026,.016],toes,body,10)
        tube("Thumb",[(sign*.315,-.355,1.025),(sign*.325,-.369,1.09),
             (sign*.293,-.377,1.105)],[.032,.028,.018],toes,body)
        # Eye globe, colored rim, pupil and small physical catchlight are separate meshes.
        ellipsoid("Eye globe",(sign*.112,-.147,1.674),(.078,.06,.078),yellow,body)
        ellipsoid("Eye green iris",(sign*.112,-.194,1.677),(.057,.023,.058),iris,body)
        ellipsoid("Eye pupil",(sign*.108,-.213,1.68),(.035,.012,.039),dark,body)
        ellipsoid("Eye glint",(sign*.108-.012,-.225,1.697),(.011,.006,.011),white,body,16,10)
        tube("Upper eyelid",[(sign*.112-.066,-.16,1.682),(sign*.112-.047,-.17,1.729),
             (sign*.112,-.168,1.748),(sign*.112+.047,-.17,1.727),(sign*.112+.067,-.16,1.681)],
             [.009,.012,.014,.012,.009],yellow,body,10)
    # Mouth follows the surface with tiny rounded corners.
    tube("Mouth crease",[(-.108,-.184,1.568),(-.075,-.217,1.552),(0,-.239,1.55),
         (.075,-.217,1.552),(.108,-.184,1.568)],[.003,.004,.004,.004,.003],toes,body,8)
    tube("Small tail",[(0,.23,.62),(0,.36,.56),(0,.44,.51),(0,.49,.50)],
         [.13,.095,.055,.005],yellow,body,20)
    glasses=empty("Accessory_glasses",root)
    for sign in (-1,1):
        x=sign*.112
        tube("Rounded frame",[(x-.074,-.226,1.638),(x-.074,-.226,1.717),
             (x-.057,-.226,1.731),(x+.057,-.226,1.731),(x+.074,-.226,1.717),
             (x+.074,-.226,1.638),(x+.057,-.226,1.625),(x-.057,-.226,1.625),
             (x-.074,-.226,1.638)],[.007]*9,frame,glasses,8)
        tube("Frame temple",[(sign*.186,-.223,1.705),(sign*.195,-.12,1.705),(sign*.19,-.02,1.69)],
             [.006]*3,frame,glasses,8)
    tube("Nose bridge",[(-.038,-.23,1.69),(0,-.235,1.70),(.038,-.23,1.69)],[.005]*3,frame,glasses,8)
    hat=empty("Accessory_hat",root)
    # A fitted cap has a distinct crown, visor, seam and small front badge.
    ellipsoid("Cap crown",(0,-.003,1.79),(.185,.17,.105),cap,hat)
    ellipsoid("Cap visor",(0,-.17,1.765),(.20,.15,.017),cap,hat)
    ellipsoid("Cap badge",(0,-.171,1.815),(.033,.008,.026),cream,hat,20,12)
    return root


def descendants(root):
    return [root]+list(root.children_recursive)


def export(root):
    OUT.mkdir(parents=True,exist_ok=True);EVIDENCE.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in descendants(root):obj.select_set(True)
    bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.fbx(filepath=str(OUT/"Nailong.fbx"),use_selection=True,
        object_types={"MESH","EMPTY","ARMATURE"},axis_forward="-Z",axis_up="Y",
        apply_unit_scale=True,add_leaf_bones=False,bake_anim=False,path_mode="COPY",embed_textures=True)
    meshes=[o for o in descendants(root) if o.type=="MESH"]
    count=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
    (EVIDENCE/"geometry.json").write_text(json.dumps({"source":"Project-authored 3D geometry from supplied visual reference",
        "triangles_including_hidden_accessories":count,"mesh_objects":len(meshes),
        "avatar":"nailong","height_m":1.84,"bpy_version":bpy.app.version_string},indent=2)+"\n")
    print("NAILONG_EXPORTED",count,"triangles",flush=True)


def render(root):
    # Preview lighting only. These objects are created after exporting, so never enter the avatar.
    for obj in descendants(root):
        if obj.name in {"Accessory_hat","Accessory_glasses"}:
            for part in descendants(obj): part.hide_render=True
    ground=material("Preview_floor",(.14,.17,.21),.65)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(ground)
    for name,position,energy,size in [
        ("Large warm key",(3,-4,5),380,4),("Soft fill",(-3,-2,3),220,3),
        ("Rim",(1,3,4),440,3)]:
        data=bpy.data.lights.new(name,"AREA");data.energy=energy;data.shape="DISK";data.size=size
        obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
        obj.location=position;obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat("-Z","Y").to_euler()
    data=bpy.data.cameras.new("Preview camera");cam=bpy.data.objects.new("Preview camera",data)
    bpy.context.collection.objects.link(cam);bpy.context.scene.camera=cam
    data.type="ORTHO";data.ortho_scale=2.35
    scene=bpy.context.scene;scene.render.engine="CYCLES";scene.cycles.samples=32
    scene.render.resolution_x=960;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    scene.world.color=(.18,.18,.18);scene.view_settings.view_transform="AgX"
    for name,location in [("front",(0,-5,2.3)),("three-quarter",(3,-5,2.2)),("side",(5,-.5,2.1))]:
        cam.location=location;cam.rotation_euler=(Vector((0,0,.95))-cam.location).to_track_quat("-Z","Y").to_euler()
        scene.render.filepath=str(EVIDENCE/(name+".png"));bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(EVIDENCE/"Nailong.blend"))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--no-render",action="store_true")
    args=parser.parse_args()
    model=build();export(model)
    if not args.no_render:render(model)
