import bpy
from bpy.props import StringProperty


class PureQ_OT_diagnostic_analyzer(bpy.types.Operator):
    """Diagnostic operator to analyze the weight transfer process step by step"""
    bl_idname = "pureq.diagnostic_analyzer"
    bl_label = "Diagnostic Analyzer"
    bl_description = "Analyze the weight transfer process step by step"
    bl_options = {'REGISTER', 'UNDO'}

    action: StringProperty(
        name="Action",
        description="Step to analyze",
        default="start"
    )

    def execute(self, context):
        print(f"\n=== DIAGNOSTIC ANALYZER: {self.action} ===")
        
        if self.action == "start":
            print("Starting diagnostic analysis...")
            self.analyze_selection(context)
        elif self.action == "before_transfer":
            print("Before weight transfer...")
            self.analyze_object_state(context.active_object, "BEFORE TRANSFER")
        elif self.action == "after_transfer":
            print("After weight transfer...")
            self.analyze_object_state(context.active_object, "AFTER TRANSFER")
        elif self.action == "full_analysis":
            print("Performing full analysis...")
            self.full_analysis(context)
        
        print(f"=== END DIAGNOSTIC: {self.action} ===\n")
        return {'FINISHED'}
    
    def analyze_selection(self, context):
        """Analyze what objects are selected"""
        print(f"Active object: {context.active_object.name if context.active_object else 'None'}")
        print(f"Selected objects: {[obj.name for obj in context.selected_objects]}")
        
        if context.active_object:
            obj = context.active_object
            print(f"Object type: {obj.type}")
            print(f"Object location: {obj.location}")
            print(f"Object scale: {obj.scale}")
            print(f"Object dimensions: {obj.dimensions}")
            print(f"Vertex count: {len(obj.data.vertices) if obj.type == 'MESH' else 'N/A'}")
            print(f"Vertex groups: {len(obj.vertex_groups) if obj.type == 'MESH' else 'N/A'}")
    
    def analyze_object_state(self, obj, stage):
        """Analyze object state at different stages"""
        if not obj or obj.type != 'MESH':
            print(f"No mesh object for {stage} analysis")
            return
        
        print(f"\n--- {stage} ANALYSIS ---")
        print(f"Object name: {obj.name}")
        print(f"Object location: {obj.location}")
        print(f"Object scale: {obj.scale}")
        print(f"Object dimensions: {obj.dimensions}")
        print(f"Vertex count: {len(obj.data.vertices)}")
        print(f"Vertex groups count: {len(obj.vertex_groups)}")
        
        # List vertex groups
        if obj.vertex_groups:
            vg_names = [vg.name for vg in obj.vertex_groups]
            print(f"Vertex group names: {vg_names}")
        
        # Check modifiers
        mod_names = [(mod.name, mod.type, getattr(mod, 'object', None).name if hasattr(mod, 'object') and mod.object else 'None') if mod.type == 'ARMATURE' else (mod.name, mod.type, 'N/A') for mod in obj.modifiers]
        print(f"Modifiers: {mod_names}")
        
        # Check if object is visible
        print(f"Object visible in viewport: {obj.visible_get()}")
        print(f"Object hide_viewport: {obj.hide_viewport}")
        
        # Check parent
        print(f"Object parent: {obj.parent.name if obj.parent else 'None'}")
        
        print("--- END ANALYSIS ---")
    
    def full_analysis(self, context):
        """Perform a complete analysis of the scene"""
        print("=== FULL SCENE ANALYSIS ===")
        
        # Analyze all objects
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                print(f"\nObject: {obj.name}")
                print(f"  Location: {obj.location}")
                print(f"  Scale: {obj.scale}")
                print(f"  Dimensions: {obj.dimensions}")
                print(f"  Vertex groups: {len(obj.vertex_groups)}")
                print(f"  Modifiers: {[mod.name + '(' + mod.type + ')' for mod in obj.modifiers]}")
                print(f"  Parent: {obj.parent.name if obj.parent else 'None'}")
                print(f"  Visible: {obj.visible_get()}")


def register():
    bpy.utils.register_class(PureQ_OT_diagnostic_analyzer)


def unregister():
    bpy.utils.unregister_class(PureQ_OT_diagnostic_analyzer)

