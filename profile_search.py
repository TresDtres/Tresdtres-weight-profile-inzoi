"""
Módulo para el sistema de búsqueda inteligente de perfiles
"""
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty
from .model_profile_db import PureQ_ProfileDatabase


class PureQ_OT_SearchProfiles(bpy.types.Operator):
    """Busca perfiles según diferentes criterios"""
    bl_idname = "pureq.search_profiles"
    bl_label = "Search Profiles"
    bl_description = "Search profiles by different criteria"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Criterios de búsqueda
    search_term: StringProperty(
        name="Search Term",
        description="Term to search in profile names, descriptions, or categories",
        default=""
    )
    
    search_category: EnumProperty(
        name="Category",
        description="Category to filter by",
        items=lambda self, context: [
            ('ALL', 'All Categories', 'Search in all categories'),
            *set((model.get('category', 'unknown'), model.get('category', 'Unknown'), f"Category: {model.get('category', 'Unknown')}") 
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Categories', 'No profiles available')],
    )
    
    search_type: EnumProperty(
        name="Model Type",
        description="Model type to filter by",
        items=lambda self, context: [
            ('ALL', 'All Types', 'Search in all types'),
            *set((model.get('model_type', 'unknown'), model.get('model_type', 'Unknown'), f"Type: {model.get('model_type', 'Unknown')}") 
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Types', 'No profiles available')],
    )
    
    search_length: EnumProperty(
        name="Length",
        description="Length to filter by",
        items=lambda self, context: [
            ('ALL', 'All Lengths', 'Search in all lengths'),
            *set((model.get('length', 'unknown'), model.get('length', 'Unknown'), f"Length: {model.get('length', 'Unknown')}") 
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Lengths', 'No profiles available')],
    )

    search_style: EnumProperty(
        name="Style",
        description="Style to filter by",
        items=lambda self, context: [
            ('ALL', 'All Styles', 'Search in all styles'),
            *set((model.get('style', 'custom'), model.get('style', 'Custom'), f"Style: {model.get('style', 'Custom')}")
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Styles', 'No profiles available')],
    )
    
    # Opciones de búsqueda
    case_sensitive: BoolProperty(
        name="Case Sensitive",
        description="Make search case sensitive",
        default=False
    )
    
    search_in_description: BoolProperty(
        name="Search in Description",
        description="Include profile descriptions in search",
        default=True
    )
    
    search_in_bones: BoolProperty(
        name="Search in Bones",
        description="Include bone names in search",
        default=False
    )
    
    def execute(self, context):
        if not self.search_term.strip() and self.search_category == 'ALL' and self.search_type == 'ALL' and self.search_length == 'ALL':
            self.report({'ERROR'}, "Please enter a search term or select a filter")
            return {'CANCELLED'}
        
        # Realizar la búsqueda
        results = self._perform_search()
        
        # Guardar resultados en la escena para mostrarlos
        context.scene.PureQ_search_results.clear()
        for key, data in results:
            item = context.scene.PureQ_search_results.add()
            item.key = key
            item.name = data.get('name', key)
            item.category = data.get('category', 'unknown')
            item.model_type = data.get('model_type', 'unknown')
            item.length = data.get('length', 'unknown')
            item.style = data.get('style', 'custom')
            item.description = data.get('description', '')
        
        self.report({'INFO'}, f"Found {len(results)} matching profiles")
        return {'FINISHED'}
    
    def _perform_search(self):
        """Realiza la búsqueda según los criterios especificados"""
        all_models = PureQ_ProfileDatabase.load_model_profiles()
        results = []
        
        # Preparar términos de búsqueda
        search_terms = []
        if self.search_term:
            search_terms = [term.strip() for term in self.search_term.lower().split() if term.strip()]
        
        for key, data in all_models.items():
            # Filtros por categoría, tipo y longitud
            if self.search_category != 'ALL' and data.get('category', '').lower() != self.search_category.lower():
                continue
            if self.search_type != 'ALL' and data.get('model_type', '').lower() != self.search_type.lower():
                continue
            if self.search_length != 'ALL' and data.get('length', '').lower() != self.search_length.lower():
                continue
            if self.search_style != 'ALL' and data.get('style', '').lower() != self.search_style.lower():
                continue
            
            # Filtros por términos de búsqueda
            if search_terms:
                match = True
                search_text = ""
                
                # Construir texto para búsqueda
                search_text += " " + key.lower()
                search_text += " " + data.get('name', '').lower()
                if self.search_in_description:
                    search_text += " " + data.get('description', '').lower()
                if self.search_in_bones:
                    profile = data.get('profile', {})
                    allowed_bones = profile.get('allowed_bones', [])
                    forbidden_bones = profile.get('forbidden_bones', [])
                    all_bones = allowed_bones + forbidden_bones
                    search_text += " " + " ".join(all_bones).lower()
                
                # Verificar si contiene los términos
                for term in search_terms:
                    if term not in search_text:
                        match = False
                        break
                
                if not match:
                    continue
            
            results.append((key, data))
        
        return results


class PureQ_SearchResultItem(bpy.types.PropertyGroup):
    """Item para los resultados de búsqueda"""
    key: StringProperty()
    name: StringProperty()
    category: StringProperty()
    model_type: StringProperty()
    length: StringProperty()
    style: StringProperty()
    description: StringProperty()


class PureQ_OT_ClearSearchResults(bpy.types.Operator):
    """Limpia los resultados de búsqueda"""
    bl_idname = "pureq.clear_search_results"
    bl_label = "Clear Results"
    bl_description = "Clear search results"
    
    def execute(self, context):
        context.scene.PureQ_search_results.clear()
        self.report({'INFO'}, "Search results cleared")
        return {'FINISHED'}


class PureQ_OT_ApplySearchResult(bpy.types.Operator):
    """Aplica un resultado de búsqueda"""
    bl_idname = "pureq.apply_search_result"
    bl_label = "Apply Profile"
    bl_description = "Apply the selected search result as current profile"
    
    result_index: IntProperty()
    
    def execute(self, context):
        if self.result_index < 0 or self.result_index >= len(context.scene.PureQ_search_results):
            self.report({'ERROR'}, "Invalid result index")
            return {'CANCELLED'}
        
        result = context.scene.PureQ_search_results[self.result_index]
        
        # Aplicar el perfil como perfil seleccionado
        context.scene.PureQ_selected_model_profile = result.key
        
        self.report({'INFO'}, f"Applied profile: {result.name}")
        return {'FINISHED'}


class PUREQ_UL_SearchResults(bpy.types.UIList):
    """UI List para mostrar los resultados de búsqueda"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Mostrar nombre y categoría
            layout.label(text=item.name, icon='FILE_BLEND')
            layout.label(text=f"{item.category}/{item.model_type}/{item.length}/{item.style}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_BLEND')


class PUREQ_PT_SearchPanel(bpy.types.Panel):
    """Panel para la búsqueda de perfiles"""
    bl_label = "Smart Profile Search"
    bl_idname = "PUREQ_PT_search_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Controles de búsqueda
        search_box = layout.box()
        search_box.label(text="Search Criteria", icon='VIEWZOOM')
        
        col = search_box.column(align=True)
        col.prop(scene, "PureQ_search_term", text="Search Term")
        
        row = col.row(align=True)
        row.prop(scene, "PureQ_search_category", text="Category")
        row.prop(scene, "PureQ_search_type", text="Type")
        row = col.row(align=True)
        row.prop(scene, "PureQ_search_length", text="Length")
        row.prop(scene, "PureQ_search_style", text="Style")
        
        # Opciones de búsqueda
        options_box = search_box.box()
        options_box.label(text="Search Options", icon='PREFERENCES')
        col = options_box.column(align=True)
        col.prop(scene, "PureQ_case_sensitive", text="Case Sensitive")
        col.prop(scene, "PureQ_search_in_description", text="Search in Description")
        col.prop(scene, "PureQ_search_in_bones", text="Search in Bone Names")
        
        # Botón de búsqueda
        search_box.operator("pureq.search_profiles", icon='VIEWZOOM')
        
        # Resultados de búsqueda
        if len(scene.PureQ_search_results) > 0:
            results_box = layout.box()
            results_box.label(text=f"Search Results ({len(scene.PureQ_search_results)})", icon='INFO')
            
            # Lista de resultados
            rows = min(8, max(3, len(scene.PureQ_search_results)))
            results_box.template_list("PUREQ_UL_SearchResults", "", scene, "PureQ_search_results", scene, "PureQ_search_results_index", rows=rows)
            
            # Controles para resultados
            if len(scene.PureQ_search_results) > 0 and scene.PureQ_search_results_index >= 0:
                idx = scene.PureQ_search_results_index
                result = scene.PureQ_search_results[idx]
                
                result_info = results_box.box()
                result_info.label(text=result.name, icon='FILE_BLEND')
                col = result_info.column(align=True)
                col.label(text=f"Key: {result.key}")
                col.label(text=f"Category: {result.category}")
                col.label(text=f"Type: {result.model_type}")
                col.label(text=f"Length: {result.length}")
                col.label(text=f"Style: {result.style}")
                if result.description:
                    col.label(text=f"Description: {result.description}")
                
                # Botones de acción
                action_row = result_info.row()
                action_row.operator("pureq.apply_search_result", text="Apply This Profile").result_index = idx
            
            # Botón para limpiar resultados
            results_box.operator("pureq.clear_search_results", icon='X', text="Clear Results")


def register():
    bpy.utils.register_class(PureQ_OT_SearchProfiles)
    bpy.utils.register_class(PureQ_SearchResultItem)
    bpy.utils.register_class(PureQ_OT_ClearSearchResults)
    bpy.utils.register_class(PureQ_OT_ApplySearchResult)
    bpy.utils.register_class(PUREQ_UL_SearchResults)
    bpy.utils.register_class(PUREQ_PT_SearchPanel)
    
    # Registrar propiedades
    bpy.types.Scene.PureQ_search_term = StringProperty(
        name="Search Term",
        description="Term to search in profiles",
        default=""
    )
    
    bpy.types.Scene.PureQ_search_category = EnumProperty(
        name="Search Category",
        description="Category to filter search",
        items=lambda self, context: [
            ('ALL', 'All Categories', 'Search in all categories'),
            *set((model.get('category', 'unknown'), model.get('category', 'Unknown'), f"Category: {model.get('category', 'Unknown')}") 
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Categories', 'No profiles available')],
    )
    
    bpy.types.Scene.PureQ_search_type = EnumProperty(
        name="Search Type",
        description="Model type to filter search",
        items=lambda self, context: [
            ('ALL', 'All Types', 'Search in all types'),
            *set((model.get('model_type', 'unknown'), model.get('model_type', 'Unknown'), f"Type: {model.get('model_type', 'Unknown')}") 
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Types', 'No profiles available')],
    )
    
    bpy.types.Scene.PureQ_search_length = EnumProperty(
        name="Search Length",
        description="Length to filter search",
        items=lambda self, context: [
            ('ALL', 'All Lengths', 'Search in all lengths'),
            *set((model.get('length', 'unknown'), model.get('length', 'Unknown'), f"Length: {model.get('length', 'Unknown')}") 
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Lengths', 'No profiles available')],
    )

    bpy.types.Scene.PureQ_search_style = EnumProperty(
        name="Search Style",
        description="Style to filter search",
        items=lambda self, context: [
            ('ALL', 'All Styles', 'Search in all styles'),
            *set((model.get('style', 'custom'), model.get('style', 'Custom'), f"Style: {model.get('style', 'Custom')}")
                 for model in PureQ_ProfileDatabase.load_model_profiles().values())
        ] if PureQ_ProfileDatabase.load_model_profiles() else [('ALL', 'All Styles', 'No profiles available')],
    )
    
    bpy.types.Scene.PureQ_case_sensitive = BoolProperty(
        name="Case Sensitive",
        description="Make search case sensitive",
        default=False
    )
    
    bpy.types.Scene.PureQ_search_in_description = BoolProperty(
        name="Search in Description",
        description="Include profile descriptions in search",
        default=True
    )
    
    bpy.types.Scene.PureQ_search_in_bones = BoolProperty(
        name="Search in Bones",
        description="Include bone names in search",
        default=False
    )
    
    bpy.types.Scene.PureQ_search_results = bpy.props.CollectionProperty(type=PureQ_SearchResultItem)
    bpy.types.Scene.PureQ_search_results_index = IntProperty(name="Index for search results", default=0)


def unregister():
    bpy.utils.unregister_class(PureQ_OT_SearchProfiles)
    bpy.utils.unregister_class(PureQ_SearchResultItem)
    bpy.utils.unregister_class(PureQ_OT_ClearSearchResults)
    bpy.utils.unregister_class(PureQ_OT_ApplySearchResult)
    bpy.utils.unregister_class(PUREQ_UL_SearchResults)
    bpy.utils.unregister_class(PUREQ_PT_SearchPanel)
    
    # Eliminar propiedades
    if hasattr(bpy.types.Scene, 'PureQ_search_term'):
        del bpy.types.Scene.PureQ_search_term
    if hasattr(bpy.types.Scene, 'PureQ_search_category'):
        del bpy.types.Scene.PureQ_search_category
    if hasattr(bpy.types.Scene, 'PureQ_search_type'):
        del bpy.types.Scene.PureQ_search_type
    if hasattr(bpy.types.Scene, 'PureQ_search_length'):
        del bpy.types.Scene.PureQ_search_length
    if hasattr(bpy.types.Scene, 'PureQ_search_style'):
        del bpy.types.Scene.PureQ_search_style
    if hasattr(bpy.types.Scene, 'PureQ_case_sensitive'):
        del bpy.types.Scene.PureQ_case_sensitive
    if hasattr(bpy.types.Scene, 'PureQ_search_in_description'):
        del bpy.types.Scene.PureQ_search_in_description
    if hasattr(bpy.types.Scene, 'PureQ_search_in_bones'):
        del bpy.types.Scene.PureQ_search_in_bones
    if hasattr(bpy.types.Scene, 'PureQ_search_results'):
        del bpy.types.Scene.PureQ_search_results
    if hasattr(bpy.types.Scene, 'PureQ_search_results_index'):
        del bpy.types.Scene.PureQ_search_results_index

