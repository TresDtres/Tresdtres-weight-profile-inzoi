"""
Módulo para detección automática de huesos y compatibilidad con diferentes rigs
"""
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty, CollectionProperty, IntProperty
from .model_profile_db import PureQ_ProfileDatabase


class PureQ_RigDetector:
    """Clase para detectar diferentes tipos de rigs y mapear huesos"""
    
    # Mapeos de huesos para diferentes rigs
    RIG_BONE_MAPPINGS = {
        "mixamo": {
            "pelvis": ["pelvis", "mixamorig:Hips", "Hips", "Root", "root"],
            "spine_01": ["spine_01", "mixamorig:Spine", "Spine", "Spine1"],
            "spine_02": ["spine_02", "mixamorig:Spine1", "Spine2"],
            "spine_03": ["spine_03", "mixamorig:Spine2", "Chest"],
            "neck_01": ["neck_01", "mixamorig:Neck", "Neck"],
            "head": ["head", "mixamorig:Head", "Head"],
            "clavicle_l": ["clavicle_l", "mixamorig:LeftShoulder", "LeftShoulder"],
            "clavicle_r": ["clavicle_r", "mixamorig:RightShoulder", "RightShoulder"],
            "upperarm_l": ["upperarm_l", "mixamorig:LeftArm", "LeftArm"],
            "upperarm_r": ["upperarm_r", "mixamorig:RightArm", "RightArm"],
            "lowerarm_l": ["lowerarm_l", "mixamorig:LeftForeArm", "LeftForeArm"],
            "lowerarm_r": ["lowerarm_r", "mixamorig:RightForeArm", "RightForeArm"],
            "hand_l": ["hand_l", "mixamorig:LeftHand", "LeftHand"],
            "hand_r": ["hand_r", "mixamorig:RightHand", "RightHand"],
            "thigh_l": ["thigh_l", "mixamorig:LeftUpLeg", "LeftUpLeg"],
            "thigh_r": ["thigh_r", "mixamorig:RightUpLeg", "RightUpLeg"],
            "calf_l": ["calf_l", "mixamorig:LeftLeg", "LeftLeg"],
            "calf_r": ["calf_r", "mixamorig:RightLeg", "RightLeg"],
            "foot_l": ["foot_l", "mixamorig:LeftFoot", "LeftFoot"],
            "foot_r": ["foot_r", "mixamorig:RightFoot", "RightFoot"],
            "ball_l": ["ball_l", "mixamorig:LeftToeBase", "LeftToeBase"],
            "ball_r": ["ball_r", "mixamorig:RightToeBase", "RightToeBase"],
            
            # Variaciones comunes de Mixamo
            "thigh_twist_01_l": ["mixamorig:LeftUpLeg", "LeftUpLeg", "Left_Hip"],
            "thigh_twist_01_r": ["mixamorig:RightUpLeg", "RightUpLeg", "Right_Hip"],
            "calf_twist_01_l": ["mixamorig:LeftLeg", "LeftLeg", "Left_Knee"],
            "calf_twist_01_r": ["mixamorig:RightLeg", "RightLeg", "Right_Knee"],
        },
        
        "PureQ": {
            "pelvis": ["pelvis"],
            "spine_01": ["spine_01"],
            "neck_01": ["neck_01"],
            "head": ["head"],
            "thigh_l": ["thigh_l"],
            "thigh_twist_01_l": ["thigh_twist_01_l"],
            "calf_l": ["calf_l"],
            "calf_twist_01_l": ["calf_twist_01_l"],
            "foot_l": ["foot_l"],
            "ball_l": ["ball_l"],
            "clavicle_l": ["clavicle_l"],
            "upperarm_l": ["upperarm_l"],
            "upperarm_twist_01_l": ["upperarm_twist_01_l"],
            "lowerarm_l": ["lowerarm_l"],
            "lowerarm_twist_01_l": ["lowerarm_twist_01_l"],
            "hand_l": ["hand_l"],
            "thumb_01_l": ["thumb_01_l"],
        },

        "epic": {
            "pelvis": ["pelvis", "root", "Root", "Hips", "hips"],
            "spine_01": ["pelvis", "spine_01", "Spine_Lower", "Lower_Spine", "spine_01_jnt"],
            "spine_02": ["spine_02", "spine_middle", "Spine_Middle", "Middle_Spine", "spine_02_jnt"],
            "spine_03": ["spine_03", "spine_upper", "Spine_Upper", "Upper_Spine", "chest", "Chest"],
            "neck_01": ["neck_01", "neck", "Neck", "neck_01_jnt"],
            "head": ["head", "Head", "HEAD", "head_jnt"],
            "clavicle_l": ["clavicle_l", "left_clavicle", "Left_Clavicle", "L_Clavicle"],
            "clavicle_r": ["clavicle_r", "right_clavicle", "Right_Clavicle", "R_Clavicle"],
            "upperarm_l": ["upperarm_l", "left_upperarm", "Left_UpperArm", "L_UpperArm", "left_shoulder", "Left_Shoulder"],
            "upperarm_r": ["upperarm_r", "right_upperarm", "Right_UpperArm", "R_UpperArm", "right_shoulder", "Right_Shoulder"],
            "lowerarm_l": ["lowerarm_l", "left_lowerarm", "Left_LowerArm", "L_LowerArm", "left_elbow", "Left_Elbow"],
            "lowerarm_r": ["lowerarm_r", "right_lowerarm", "Right_LowerArm", "R_LowerArm", "right_elbow", "Right_Elbow"],
            "hand_l": ["hand_l", "left_hand", "Left_Hand", "L_Hand"],
            "hand_r": ["hand_r", "right_hand", "Right_Hand", "R_Hand"],
            "thigh_l": ["thigh_l", "left_thigh", "Left_Thigh", "L_Thigh", "left_hip", "Left_Hip"],
            "thigh_r": ["thigh_r", "right_thigh", "Right_Thigh", "R_Thigh", "right_hip", "Right_Hip"],
            "calf_l": ["calf_l", "left_calf", "Left_Calf", "L_Calf", "left_knee", "Left_Knee"],
            "calf_r": ["calf_r", "right_calf", "Right_Calf", "R_Calf", "right_knee", "Right_Knee"],
            "foot_l": ["foot_l", "left_foot", "Left_Foot", "L_Foot"],
            "foot_r": ["foot_r", "right_foot", "Right_Foot", "R_Foot"],
            "ball_l": ["ball_l", "left_ball", "Left_Ball", "L_Ball", "left_toe", "Left_Toe"],
            "ball_r": ["ball_r", "right_ball", "Right_Ball", "R_Ball", "right_toe", "Right_Toe"],
        },
        
        "cc": {
            "pelvis": ["CC_Base_Hip"],
            "spine_01": ["CC_Base_Waist"],
            "spine_02": ["CC_Base_Spine01"],
            "spine_03": ["CC_Base_Spine02"],
            "neck_01": ["CC_Base_Neck"],
            "head": ["CC_Base_Head"],
            "clavicle_l": ["CC_Base_L_Clavicle"],
            "upperarm_l": ["CC_Base_L_UpperArm"],
            "lowerarm_l": ["CC_Base_L_Forearm"],
            "hand_l": ["CC_Base_L_Hand"],
            "thigh_l": ["CC_Base_L_Thigh"],
            "calf_l": ["CC_Base_L_Calf"],
            "foot_l": ["CC_Base_L_Foot"],
            "ball_l": ["CC_Base_L_ToeBase"],
        },

        "metahuman": {
            "pelvis": ["pelvis", "root", "Root", "Hips", "hips", "c_root.x"],
            "spine_01": ["pelvis", "spine_01", "Spine1", "spine_01_jnt", "c_spine01.x"],
            "spine_02": ["spine_02", "Spine2", "spine_02_jnt", "c_spine02.x"],
            "spine_03": ["spine_03", "Spine3", "chest", "Chest", "c_spine03.x"],
            "neck_01": ["neck_01", "Neck", "neck_01_jnt", "c_neck.x"],
            "head": ["head", "Head", "HEAD", "head_jnt", "c_head.x"],
            "clavicle_l": ["clavicle_l", "LeftCollar", "l_clavicle", "c_clavicle.l"],
            "clavicle_r": ["clavicle_r", "RightCollar", "r_clavicle", "c_clavicle.r"],
            "upperarm_l": ["upperarm_l", "LeftShoulder", "l_shoulder", "c_upperarm.l"],
            "upperarm_r": ["upperarm_r", "RightShoulder", "r_shoulder", "c_upperarm.r"],
            "lowerarm_l": ["lowerarm_l", "LeftElbow", "l_elbow", "c_lowerarm.l"],
            "lowerarm_r": ["lowerarm_r", "RightElbow", "r_elbow", "c_lowerarm.r"],
            "hand_l": ["hand_l", "LeftWrist", "l_wrist", "c_hand.l"],
            "hand_r": ["hand_r", "RightWrist", "r_wrist", "c_hand.r"],
            "thigh_l": ["thigh_l", "LeftUpLeg", "l_hip", "c_thigh.l"],
            "thigh_r": ["thigh_r", "RightUpLeg", "r_hip", "c_thigh.r"],
            "calf_l": ["calf_l", "LeftLeg", "l_knee", "c_calf.l"],
            "calf_r": ["calf_r", "RightLeg", "r_knee", "c_calf.r"],
            "foot_l": ["foot_l", "LeftFoot", "l_ankle", "c_foot.l"],
            "foot_r": ["foot_r", "RightFoot", "r_ankle", "c_foot.r"],
            "ball_l": ["ball_l", "LeftToeBase", "l_toe", "c_ball.l"],
            "ball_r": ["ball_r", "RightToeBase", "r_toe", "c_ball.r"],
        },
        
        "generic": {
            # Mapeo genérico para rigs personalizados
            "pelvis": ["pelvis", "hips", "hip", "root", "Root", "Hips", "Pelvis", "pelvis", "Body", "body"],
            "spine_01": ["spine", "Spine", "spine1", "Spine1", "lower_spine", "LowerSpine", "torso", "Torso"],
            "spine_02": ["spine1", "Spine2", "middle_spine", "MiddleSpine", "chest", "Chest"],
            "spine_03": ["spine2", "Spine3", "upper_spine", "UpperSpine", "upper_chest", "UpperChest"],
            "neck_01": ["neck", "Neck", "neck1", "cervical", "Cervical"],
            "head": ["head", "Head", "HEAD", "skull", "Skull"],
            "clavicle_l": ["clavicle", "Clavicle", "shoulder_l", "Shoulder_L", "left_shoulder", "LeftShoulder"],
            "clavicle_r": ["clavicle", "Clavicle", "shoulder_r", "Shoulder_R", "right_shoulder", "RightShoulder"],
            "upperarm_l": ["upperarm", "UpperArm", "arm_l", "Arm_L", "left_arm", "LeftArm", "upper_arm_l", "LeftUpperArm"],
            "upperarm_r": ["upperarm", "UpperArm", "arm_r", "Arm_R", "right_arm", "RightArm", "upper_arm_r", "RightUpperArm"],
            "lowerarm_l": ["lowerarm", "LowerArm", "forearm_l", "Forearm_L", "left_forearm", "LeftForearm"],
            "lowerarm_r": ["lowerarm", "LowerArm", "forearm_r", "Forearm_R", "right_forearm", "RightForearm"],
            "hand_l": ["hand_l", "Hand_L", "left_hand", "LeftHand", "wrist_l", "LeftWrist"],
            "hand_r": ["hand_r", "Hand_R", "right_hand", "RightHand", "wrist_r", "RightWrist"],
            "thigh_l": ["thigh", "Thigh", "leg_l", "Leg_L", "left_leg", "LeftLeg", "hip_l", "LeftHip"],
            "thigh_r": ["thigh", "Thigh", "leg_r", "Leg_R", "right_leg", "RightLeg", "hip_r", "RightHip"],
            "calf_l": ["calf", "Calf", "knee_l", "Knee_L", "left_knee", "LeftKnee", "shin_l", "LeftShin"],
            "calf_r": ["calf", "Calf", "knee_r", "Knee_R", "right_knee", "RightKnee", "shin_r", "RightShin"],
            "foot_l": ["foot_l", "Foot_L", "left_foot", "LeftFoot", "ankle_l", "LeftAnkle"],
            "foot_r": ["foot_r", "Foot_R", "right_foot", "RightFoot", "ankle_r", "RightAnkle"],
            "ball_l": ["ball", "Ball", "toe_l", "Toe_L", "left_toe", "LeftToe", "toe_base_l"],
            "ball_r": ["ball", "Ball", "toe_r", "Toe_R", "right_toe", "RightToe", "toe_base_r"],
        }
    }
    
    @classmethod
    def detect_rig_type(cls, armature_obj):
        """Detecta el tipo de rig basado en los nombres de huesos"""
        if not armature_obj or armature_obj.type != 'ARMATURE':
            return "unknown"
        
        bone_names = {bone.name.lower() for bone in armature_obj.data.bones}
        
        # Contar coincidencias con cada tipo de rig
        rig_scores = {}
        for rig_type, bone_mapping in cls.RIG_BONE_MAPPINGS.items():
            score = 0
            for PureQi_bone, possible_names in bone_mapping.items():
                for name in possible_names:
                    if name.lower() in bone_names:
                        score += 1
                        break  # Contar solo una coincidencia por hueso PureQ
            rig_scores[rig_type] = score
        
        # Devolver el tipo de rig con más coincidencias
        if rig_scores:
            best_rig = max(rig_scores, key=rig_scores.get)
            if rig_scores[best_rig] > 0:  # Solo si hay al menos una coincidencia
                return best_rig
        
        return "generic"  # Por defecto, usar mapeo genérico
    
    @classmethod
    def map_bones_to_PureQi(cls, armature_obj, target_rig_type=None):
        """Mapea los huesos del armature a los nombres PureQ estándar"""
        if not armature_obj or armature_obj.type != 'ARMATURE':
            return {}
        
        if not target_rig_type:
            target_rig_type = cls.detect_rig_type(armature_obj)
        
        if target_rig_type not in cls.RIG_BONE_MAPPINGS:
            target_rig_type = "generic"
        
        bone_mapping = {}
        bone_name_map = {bone.name.lower(): bone.name for bone in armature_obj.data.bones}
        
        for PureQi_bone, possible_names in cls.RIG_BONE_MAPPINGS[target_rig_type].items():
            # Buscar el primer nombre que coincida
            for name in possible_names:
                if name.lower() in bone_name_map:
                    bone_mapping[PureQi_bone] = bone_name_map[name.lower()]
                    break
        
        return bone_mapping
    
    @classmethod
    def get_available_bones_for_rig(cls, armature_obj, target_rig_type=None):
        """Obtiene los huesos disponibles en el rig para mapear"""
        if not armature_obj or armature_obj.type != 'ARMATURE':
            return []
        
        if not target_rig_type:
            target_rig_type = cls.detect_rig_type(armature_obj)
        
        if target_rig_type not in cls.RIG_BONE_MAPPINGS:
            target_rig_type = "generic"
        
        available_bones = []
        bone_names = {bone.name.lower(): bone.name for bone in armature_obj.data.bones}
        
        for PureQi_bone, possible_names in cls.RIG_BONE_MAPPINGS[target_rig_type].items():
            for name in possible_names:
                if name.lower() in bone_names:
                    available_bones.append((PureQi_bone, bone_names[name.lower()]))
                    break
        
        return available_bones


class PureQ_OT_DetectRig(bpy.types.Operator):
    """Detecta el tipo de rig y mapea los huesos"""
    bl_idname = "pureq.detect_rig"
    bl_label = "Detect Rig"
    bl_description = "Detect the rig type and map bones accordingly"
    
    def execute(self, context):
        obj = context.active_object
        
        # Buscar el armature asociado
        armature_obj = None
        if obj and obj.type == 'MESH':
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object:
                    armature_obj = modifier.object
                    break
        elif obj and obj.type == 'ARMATURE':
            armature_obj = obj
        
        if not armature_obj:
            self.report({'ERROR'}, "No armature found or selected")
            return {'CANCELLED'}
        
        # Detectar el tipo de rig
        rig_type = PureQ_RigDetector.detect_rig_type(armature_obj)
        
        # Mapear huesos
        bone_mapping = PureQ_RigDetector.map_bones_to_PureQi(armature_obj, rig_type)
        
        # Guardar información en la escena para su uso posterior
        context.scene.PureQ_detected_rig_type = rig_type
        context.scene.PureQ_bone_mapping.clear()
        
        for PureQi_bone, actual_bone in bone_mapping.items():
            item = context.scene.PureQ_bone_mapping.add()
            item.PureQi_name = PureQi_bone
            item.actual_name = actual_bone
            item.is_mapped = True
        
        self.report({'INFO'}, f"Detected rig type: {rig_type}, mapped {len(bone_mapping)} bones")
        return {'FINISHED'}


class PureQ_BoneMappingItem(bpy.types.PropertyGroup):
    """Item para el mapeo de huesos"""
    PureQi_name: StringProperty(name="PureQ Name")
    actual_name: StringProperty(name="Actual Bone Name")
    is_mapped: BoolProperty(name="Is Mapped", default=True)


class PureQ_OT_CreateAdaptedProfile(bpy.types.Operator):
    """Crea un perfil adaptado al rig detectado"""
    bl_idname = "pureq.create_adapted_profile"
    bl_label = "Create Adapted Profile"
    bl_description = "Create a profile adapted to the detected rig"
    
    profile_name: StringProperty(
        name="Profile Name",
        description="Name for the new adapted profile",
        default="Adapted_Profile"
    )
    
    profile_category: EnumProperty(
        name="Category",
        description="Category for the new profile",
        items=[
            ('skirt', 'Skirt', 'Skirt profile'),
            ('shorts', 'Shorts', 'Shorts profile'),
            ('pants', 'Pants', 'Pants profile'),
            ('dress', 'Dress', 'Dress profile'),
            ('top', 'Top', 'Top profile'),
            ('custom', 'Custom', 'Custom profile'),
        ],
        default='custom'
    )
    
    def execute(self, context):
        if not self.profile_name.strip():
            self.report({'ERROR'}, "Profile name cannot be empty")
            return {'CANCELLED'}
        
        # Obtener el mapeo de huesos
        bone_mapping = {}
        for item in context.scene.PureQ_bone_mapping:
            if item.is_mapped:
                bone_mapping[item.PureQi_name] = item.actual_name
        
        if not bone_mapping:
            self.report({'ERROR'}, "No bone mapping available. Run 'Detect Rig' first.")
            return {'CANCELLED'}
        
        # Crear perfil basado en categoría
        profile_data = self._create_profile_for_category(self.profile_category, bone_mapping)
        
        # Añadir el perfil a la base de datos
        model_key = PureQ_ProfileDatabase.add_model_profile(
            self.profile_name,
            self.profile_category,
            "auto",  # longitud automática
            self.profile_category,  # tipo coincide con categoría
            f"Auto-generated profile for {context.scene.PureQ_detected_rig_type} rig",
            profile_data
        )
        
        self.report({'INFO'}, f"Created adapted profile: {model_key}")
        return {'FINISHED'}
    
    def _create_profile_for_category(self, category, bone_mapping):
        """Crea un perfil de huesos basado en la categoría"""
        # Obtener huesos relevantes del mapeo
        pelvis_bone = self._find_bone_in_mapping(bone_mapping, ['pelvis'])
        thigh_l_bone = self._find_bone_in_mapping(bone_mapping, ['thigh_l', 'upper_leg_l', 'hip_l'])
        thigh_r_bone = self._find_bone_in_mapping(bone_mapping, ['thigh_r', 'upper_leg_r', 'hip_r'])
        calf_l_bone = self._find_bone_in_mapping(bone_mapping, ['calf_l', 'lower_leg_l', 'knee_l'])
        calf_r_bone = self._find_bone_in_mapping(bone_mapping, ['calf_r', 'lower_leg_r', 'knee_r'])
        
        # Crear perfil según categoría
        if category in ['skirt', 'shorts', 'dress']:
            # Perfiles para prendas inferiores
            allowed_bones = [bone for bone in [pelvis_bone, thigh_l_bone, thigh_r_bone, calf_l_bone, calf_r_bone] if bone]
        elif category in ['top', 'jacket']:
            # Perfiles para prendas superiores
            allowed_bones = [bone for bone in [pelvis_bone] if bone]
        else:
            # Perfil genérico
            allowed_bones = list(set(bone_mapping.values()))  # Todos los huesos mapeados
        
        # Añadir huesos comunes que deberían estar en todos los perfiles
        common_bones = ['root', 'Root', 'Hips', 'hips', 'body', 'Body']
        for common_bone in common_bones:
            if common_bone in bone_mapping.values() and common_bone not in allowed_bones:
                allowed_bones.append(common_bone)
        
        profile_data = {
            "allowed_bones": allowed_bones,
            "forbidden_bones": [],  # Por defecto, ninguno prohibido
            "min_weight": 0.001,
            "max_influences": 4
        }
        
        return profile_data
    
    def _find_bone_in_mapping(self, bone_mapping, possible_names):
        """Encuentra un hueso en el mapeo usando posibles nombres"""
        for name in possible_names:
            if name in bone_mapping:
                return bone_mapping[name]
        return None


class PUREQ_PT_RigDetectionPanel(bpy.types.Panel):
    """Panel para la detección de rigs"""
    bl_label = "Rig Detection & Adaptation"
    bl_idname = "PUREQ_PT_rig_detection_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Información del rig detectado
        if scene.PureQ_detected_rig_type != "unknown":
            rig_info = layout.box()
            rig_info.label(text=f"Detected Rig: {scene.PureQ_detected_rig_type}", icon='ARMATURE_DATA')
        else:
            rig_info = layout.box()
            rig_info.label(text="No rig detected", icon='ERROR')
        
        # Botón para detectar rig
        detect_row = layout.row()
        detect_row.operator("pureq.detect_rig", icon='VIEWZOOM')
        
        # Mostrar mapeo de huesos si existe
        if len(scene.PureQ_bone_mapping) > 0:
            mapping_box = layout.box()
            mapping_box.label(text="Bone Mapping", icon='GROUP_BONE')
            
            # Contar huesos mapeados
            mapped_count = sum(1 for item in scene.PureQ_bone_mapping if item.is_mapped)
            mapping_box.label(text=f"Mapped: {mapped_count}/{len(scene.PureQ_bone_mapping)}")
            
            # Crear perfil adaptado
            create_box = layout.box()
            create_box.label(text="Create Adapted Profile", icon='FILE_NEW')
            
            col = create_box.column(align=True)
            col.prop(scene, "PureQ_new_adapted_profile_name", text="Name")
            col.prop(scene, "PureQ_new_adapted_profile_category", text="Category")
            
            create_box.operator("pureq.create_adapted_profile", icon='FILE_TICK')


def register():
    bpy.utils.register_class(PureQ_BoneMappingItem)
    bpy.utils.register_class(PureQ_OT_DetectRig)
    bpy.utils.register_class(PureQ_OT_CreateAdaptedProfile)
    bpy.utils.register_class(PUREQ_PT_RigDetectionPanel)
    
    # Registrar propiedades
    bpy.types.Scene.PureQ_detected_rig_type = StringProperty(
        name="Detected Rig Type",
        description="Type of rig detected",
        default="unknown"
    )
    
    bpy.types.Scene.PureQ_bone_mapping = CollectionProperty(type=PureQ_BoneMappingItem)
    
    bpy.types.Scene.PureQ_new_adapted_profile_name = StringProperty(
        name="Adapted Profile Name",
        description="Name for the new adapted profile",
        default="Adapted_Profile"
    )
    
    bpy.types.Scene.PureQ_new_adapted_profile_category = EnumProperty(
        name="Profile Category",
        description="Category for the adapted profile",
        items=[
            ('skirt', 'Skirt', 'Skirt profile'),
            ('shorts', 'Shorts', 'Shorts profile'),
            ('pants', 'Pants', 'Pants profile'),
            ('dress', 'Dress', 'Dress profile'),
            ('top', 'Top', 'Top profile'),
            ('custom', 'Custom', 'Custom profile'),
        ],
        default='custom'
    )


def unregister():
    bpy.utils.unregister_class(PureQ_BoneMappingItem)
    bpy.utils.unregister_class(PureQ_OT_DetectRig)
    bpy.utils.unregister_class(PureQ_OT_CreateAdaptedProfile)
    bpy.utils.unregister_class(PUREQ_PT_RigDetectionPanel)
    
    # Eliminar propiedades
    if hasattr(bpy.types.Scene, 'PureQ_detected_rig_type'):
        delattr(bpy.types.Scene, 'PureQ_detected_rig_type')
    if hasattr(bpy.types.Scene, 'PureQ_bone_mapping'):
        delattr(bpy.types.Scene, 'PureQ_bone_mapping')
    if hasattr(bpy.types.Scene, 'PureQ_new_adapted_profile_name'):
        delattr(bpy.types.Scene, 'PureQ_new_adapted_profile_name')
    if hasattr(bpy.types.Scene, 'PureQ_new_adapted_profile_category'):
        delattr(bpy.types.Scene, 'PureQ_new_adapted_profile_category')

