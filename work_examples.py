"""
Ejemplos de trabajo para el addon PureQ Weight Transfer

Este archivo contiene ejemplos de código que demuestran cómo usar el addon
con diferentes tipos de avatares y prendas para diferentes situaciones de transferencia de pesos.
"""

import bpy
import os
import bmesh
from mathutils import Vector


def create_example_avatar():
    """Crea un avatar de ejemplo con huesos básicos"""
    # Crear armature
    armature_data = bpy.data.armatures.new(name="ExampleAvatarArmature")
    armature_obj = bpy.data.objects.new("ExampleAvatar", armature_data)
    
    # Añadir a la escena
    bpy.context.collection.objects.link(armature_obj)
    bpy.context.view_layer.objects.active = armature_obj
    
    # Entrar en modo edición para crear huesos
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Crear huesos básicos
    bones = {
        "pelvis": (0, 0, 0),
        "spine_01": (0, 0, 0.1),
        "spine_02": (0, 0, 0.2),
        "spine_03": (0, 0, 0.3),
        "thigh_l": (-0.05, 0, 0.05),
        "thigh_r": (0.05, 0, 0.05),
        "calf_l": (-0.05, 0, -0.1),
        "calf_r": (0.05, 0, -0.1),
        "foot_l": (-0.05, 0, -0.3),
        "foot_r": (0.05, 0, -0.3),
    }
    
    edit_bones = armature_obj.data.edit_bones
    for bone_name, position in bones.items():
        bone = edit_bones.new(bone_name)
        bone.head = position
        bone.tail = (position[0], position[1], position[2] - 0.1 if "foot" in bone_name else position[2] + 0.1)
    
    # Salir del modo edición
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Crear malla de ejemplo para el avatar
    mesh_data = bpy.data.meshes.new("ExampleAvatarBody")
    mesh_obj = bpy.data.objects.new("ExampleAvatarBody", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)
    
    # Crear malla simple (cilindro)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, radius=0.1)
    bm.to_mesh(mesh_data)
    bm.free()
    
    # Añadir modificador de armature
    modifier = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    modifier.object = armature_obj
    
    # Crear grupos de vértices
    for bone_name in bones.keys():
        mesh_obj.vertex_groups.new(name=bone_name)
    
    return armature_obj, mesh_obj


def create_example_skirt():
    """Crea una prenda de ejemplo (falda)"""
    # Crear malla de falda
    mesh_data = bpy.data.meshes.new("ExampleSkirt")
    mesh_obj = bpy.data.objects.new("ExampleSkirt", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)
    
    # Crear una malla de falda simple
    bm = bmesh.new()
    
    # Crear anillos de vértices para la falda
    segments = 16
    levels = 4
    
    # Anillo superior (cintura)
    top_ring = []
    for i in range(segments):
        angle = 2 * 3.14159 * i / segments
        x = 0.1 * bpy.mathutils.cos(angle)
        y = 0.1 * bpy.mathutils.sin(angle)
        z = 0.05
        vert = bm.verts.new((x, y, z))
        top_ring.append(vert)
    
    # Anillos intermedios
    rings = [top_ring]
    for level in range(1, levels):
        ring = []
        for i in range(segments):
            angle = 2 * 3.14159 * i / segments
            scale = 1.0 + level * 0.3  # Aumenta el tamaño hacia abajo
            x = 0.1 * scale * bpy.mathutils.cos(angle)
            y = 0.1 * scale * bpy.mathutils.sin(angle)
            z = 0.05 - level * 0.15  # Más bajo en niveles inferiores
            vert = bm.verts.new((x, y, z))
            ring.append(vert)
        rings.append(ring)
    
    # Crear caras entre anillos
    for level in range(len(rings) - 1):
        for i in range(segments):
            v1 = rings[level][i]
            v2 = rings[level][(i + 1) % segments]
            v3 = rings[level + 1][(i + 1) % segments]
            v4 = rings[level + 1][i]

            bm.faces.new([v1, v2, v3, v4])

    bm.to_mesh(mesh_data)
    bm.free()

    # Posicionar la falda
    mesh_obj.location = (0, 0, 0.1)  # Ligeramente encima del suelo

    return mesh_obj


def example_basic_transfer():
    """Ejemplo básico de transferencia de pesos"""
    print("=== Ejemplo Básico de Transferencia de Pesos ===")

    # Crear avatar y prenda de ejemplo
    armature_obj, avatar_obj = create_example_avatar()
    clothing_obj = create_example_skirt()

    print(f"Avatar creado: {avatar_obj.name}")
    print(f"Prenda creada: {clothing_obj.name}")

    # Simular la transferencia de pesos
    print("Simulando transferencia de pesos...")

    # Seleccionar la prenda
    bpy.ops.object.select_all(action='DESELECT')
    clothing_obj.select_set(True)
    bpy.context.view_layer.objects.active = clothing_obj

    print("Prenda seleccionada para transferencia de pesos")

    # En un entorno real, aquí se llamaría al operador de transferencia
    # bpy.ops.pureq.transfer_weights()

    print("Transferencia de pesos simulada completada")
    print("")


def example_mixamo_compatibility():
    """Ejemplo de compatibilidad con Mixamo"""
    print("=== Ejemplo de Compatibilidad con Mixamo ===")

    # Crear armature con nombres de huesos de Mixamo
    armature_data = bpy.data.armatures.new(name="MixamoArmature")
    armature_obj = bpy.data.objects.new("MixamoAvatar", armature_data)
    bpy.context.collection.objects.link(armature_obj)

    # Entrar en modo edición
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')

    # Crear huesos con nombres de Mixamo
    mixamo_bones = {
        "mixamorig:Hips": (0, 0, 0.9),
        "mixamorig:Spine": (0, 0, 1.0),
        "mixamorig:Spine1": (0, 0, 1.1),
        "mixamorig:LeftUpLeg": (-0.08, 0, 0.9),
        "mixamorig:RightUpLeg": (0.08, 0, 0.9),
        "mixamorig:LeftLeg": (-0.08, 0, 0.4),
        "mixamorig:RightLeg": (0.08, 0, 0.4),
        "mixamorig:LeftFoot": (-0.08, 0, 0.1),
        "mixamorig:RightFoot": (0.08, 0, 0.1),
    }

    edit_bones = armature_obj.data.edit_bones
    for bone_name, position in mixamo_bones.items():
        bone = edit_bones.new(bone_name)
        bone.head = position
        bone.tail = (position[0], position[1], position[2] - 0.3 if "Foot" in bone_name else position[2] - 0.1)

    # Salir del modo edición
    bpy.ops.object.mode_set(mode='OBJECT')

    # Crear malla de ejemplo
    mesh_data = bpy.data.meshes.new("MixamoAvatarBody")
    mesh_obj = bpy.data.objects.new("MixamoAvatarBody", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)

    # Crear malla simple
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, radius=0.1)
    bm.to_mesh(mesh_data)
    bm.free()

    # Añadir modificador de armature
    modifier = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    modifier.object = armature_obj

    # Crear grupos de vértices con nombres de Mixamo
    for bone_name in mixamo_bones.keys():
        mesh_obj.vertex_groups.new(name=bone_name)

    print(f"Avatar Mixamo creado: {mesh_obj.name}")
    print(f"Huesos Mixamo detectados: {list(mixamo_bones.keys())}")

    # Crear una prenda de ejemplo
    clothing_obj = create_example_skirt()
    clothing_obj.location = (0, 0, 0.9)  # Colocar en la altura de la cadera

    print(f"Prenda para Mixamo creada: {clothing_obj.name}")

    # Demostrar detección de rig
    print("Sistema de detección de rig debería identificar este como rig Mixamo")
    print("")


def example_profile_creation():
    """Ejemplo de creación de perfiles personalizados"""
    print("=== Ejemplo de Creación de Perfiles Personalizados ===")

    # Simular creación de perfil para falda corta
    profile_data = {
        "allowed_bones": [
            "pelvis",
            "thigh_l", "thigh_r",
            "calf_l", "calf_r"
        ],
        "forbidden_bones": [
            "foot_l", "foot_r",
            "ball_l", "ball_r"
        ],
        "min_weight": 0.001,
        "max_influences": 4
    }

    print("Perfil para falda corta creado:")
    print(f"- Huesos permitidos: {profile_data['allowed_bones']}")
    print(f"- Huesos prohibidos: {profile_data['forbidden_bones']}")
    print(f"- Peso mínimo: {profile_data['min_weight']}")
    print(f"- Máximo de influencias: {profile_data['max_influences']}")

    # Simular guardado del perfil
    print("Perfil guardado en la base de datos de perfiles")
    print("")


def example_avatar_organization():
    """Ejemplo de organización por avatar"""
    print("=== Ejemplo de Organización por Avatar ===")

    # Simular creación de carpeta para avatar específico
    avatar_name = "Female_Character_A"
    print(f"Carpeta creada para avatar: {avatar_name}")

    # Simular perfiles específicos para este avatar
    avatar_specific_profiles = [
        "Female_Skirt_Long",
        "Female_Skirt_Medium",
        "Female_Skirt_Short",
        "Female_Shorts",
        "Female_Dress"
    ]

    print(f"Perfiles específicos para {avatar_name}:")
    for profile in avatar_specific_profiles:
        print(f"  - {profile}")

    print("Los perfiles se almacenan en una carpeta específica para evitar conflictos")
    print("")


def run_all_examples():
    """Ejecuta todos los ejemplos"""
    print("PureQ Weight Transfer - Ejemplos de Trabajo")
    print("=" * 50)

    example_basic_transfer()
    example_mixamo_compatibility()
    example_profile_creation()
    example_avatar_organization()

    print("=" * 50)
    print("¡Todos los ejemplos se han ejecutado!")
    print("")
    print("Instrucciones para usar:")
    print("1. Crea o importa tu avatar con huesos nombrados apropiadamente")
    print("2. Crea o importa tu prenda/clothing")
    print("3. Usa el panel 'PureQ Weight Transfer' para transferir pesos")
    print("4. Selecciona el perfil adecuado para tu tipo de prenda")
    print("5. Usa las herramientas de organización si trabajas con múltiples avatares")


class PureQ_OT_RunExamples(bpy.types.Operator):
    """Ejecuta ejemplos de trabajo del addon"""
    bl_idname = "pureq.run_examples"
    bl_label = "Run Examples"
    bl_description = "Run examples demonstrating how to use the addon"

    def execute(self, context):
        run_all_examples()
        self.report({'INFO'}, "Examples executed. Check console for details.")
        return {'FINISHED'}


def draw_examples_panel(self, context):
    layout = self.layout
    layout.label(text="Examples", icon='TEXT')
    layout.operator("pureq.run_examples", icon='PLAY')


def register_example_scripts():
    """Registra scripts de ejemplo como operadores"""
    bpy.utils.register_class(PureQ_OT_RunExamples)

    # Añadir al panel de la interfaz
    try:
        from bpy.types import VIEW3D_PT_tools_weightpaint
        VIEW3D_PT_tools_weightpaint.append(draw_examples_panel)
    except ImportError:
        pass  # El panel no existe en esta versión de Blender, ignorar


def unregister_example_scripts():
    """Desregistra scripts de ejemplo"""
    try:
        from bpy.types import VIEW3D_PT_tools_weightpaint
        VIEW3D_PT_tools_weightpaint.remove(draw_examples_panel)
    except:
        pass  # Si no se había añadido, no pasa nada

    try:
        bpy.utils.unregister_class(PureQ_OT_RunExamples)
    except:
        pass


if __name__ == "__main__":
    # Si se ejecuta este script directamente, correr los ejemplos
    run_all_examples()

