import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty, IntProperty


class PureQ_OT_auto_clean_vertex_groups(bpy.types.Operator):
    """Automatically clean vertex groups by removing unused groups and low-weight vertices"""
    bl_idname = "pureq.auto_clean_vertex_groups"
    bl_label = "Auto Clean Vertex Groups"
    bl_description = "Automatically clean vertex groups by removing unused groups and low-weight vertices"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Weight Threshold",
        description="Minimum weight value to keep vertices",
        default=0.001,
        min=0.0,
        max=1.0
    )

    remove_unused_groups: BoolProperty(
        name="Remove Unused Groups",
        description="Remove vertex groups that have no vertices assigned",
        default=True
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        initial_group_count = len(obj.vertex_groups)
        initial_vertex_count = len(obj.data.vertices)

        # Remove unused vertex groups
        if self.remove_unused_groups:
            groups_to_remove = []
            for vg in obj.vertex_groups:
                has_vertices = False
                for v in obj.data.vertices:
                    for g in v.groups:
                        if g.group == vg.index and g.weight > self.threshold:
                            has_vertices = True
                            break
                    if has_vertices:
                        break
                if not has_vertices:
                    groups_to_remove.append(vg)

            for vg in reversed(groups_to_remove):
                obj.vertex_groups.remove(vg)

        # Clean low-weight vertices using Blender's built-in operator
        if obj.vertex_groups:
            bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=self.threshold)

        final_group_count = len(obj.vertex_groups)
        final_vertex_count = len(obj.data.vertices)

        self.report({'INFO'},
                   f"Auto clean completed: {initial_group_count - final_group_count} groups removed, "
                   f"vertices cleaned from {initial_vertex_count} to {final_vertex_count}")

        return {'FINISHED'}


class PureQ_OT_select_low_weight_vertices(bpy.types.Operator):
    """Select vertices with weights below threshold for manual editing"""
    bl_idname = "pureq.select_low_weight_vertices"
    bl_label = "Select Low Weight Vertices"
    bl_description = "Select vertices with weights below threshold for manual editing"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Weight Threshold",
        description="Select vertices with weights below this value",
        default=0.01,
        min=0.0,
        max=1.0
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        # Switch to edit mode to select vertices
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        # Deselect all first
        bpy.ops.mesh.select_all(action='DESELECT')

        # Select vertices with low weights
        bpy.ops.object.mode_set(mode='OBJECT')  # Need to be in object mode to access vertex groups

        low_weight_count = 0
        for v in obj.data.vertices:
            for g in v.groups:
                if g.weight < self.threshold:
                    v.select = True
                    low_weight_count += 1
                    break  # Only need to select once per vertex

        # Back to edit mode to show selection
        bpy.ops.object.mode_set(mode='EDIT')

        self.report({'INFO'}, f"Selected {low_weight_count} vertices with weights below {self.threshold}")

        return {'FINISHED'}


class PureQ_OT_merge_similar_vertex_groups(bpy.types.Operator):
    """Merge similar vertex groups that represent the same bone with different names"""
    bl_idname = "pureq.merge_similar_vertex_groups"
    bl_label = "Merge Similar Vertex Groups"
    bl_description = "Merge vertex groups that represent the same bone with different names"
    bl_options = {'REGISTER', 'UNDO'}

    merge_threshold: FloatProperty(
        name="Merge Threshold",
        description="Minimum overlap required to merge groups (0.0 to 1.0)",
        default=0.8,
        min=0.0,
        max=1.0
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        # Dictionary to group similar vertex groups
        bone_groups = {}
        for vg in obj.vertex_groups:
            # Extract base bone name (remove suffixes like _L, _R, _l, _r)
            base_name = vg.name.lower()
            if base_name.endswith(('_l', '_r', '_left', '_right', '.l', '.r')):
                base_name = base_name.rsplit('_l', 1)[0].rsplit('_r', 1)[0].rsplit('_left', 1)[0].rsplit('_right', 1)[0]
                base_name = base_name.rsplit('.l', 1)[0].rsplit('.r', 1)[0]

            if base_name not in bone_groups:
                bone_groups[base_name] = []
            bone_groups[base_name].append(vg)

        # Merge groups that have similar names
        merge_count = 0
        for base_name, groups in bone_groups.items():
            if len(groups) > 1:
                # Use the first group as destination, merge others into it
                dest_group = groups[0]
                for src_group in groups[1:]:
                    # Use vertex weight mix modifier to merge weights
                    mix_mod = obj.modifiers.new(name="TempMerge", type='VERTEX_WEIGHT_MIX')
                    mix_mod.vertex_group_a = dest_group.name  # Destination
                    mix_mod.vertex_group_b = src_group.name   # Source
                    mix_mod.mix_mode = 'ADD'
                    mix_mod.mix_set = 'B'  # Apply to vertices in source group

                    # Apply the modifier
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier=mix_mod.name)

                    # Remove the source group
                    obj.vertex_groups.remove(src_group)
                    merge_count += 1

        self.report({'INFO'}, f"Merged {merge_count} similar vertex groups")

        return {'FINISHED'}


class PureQ_OT_compensate_weights(bpy.types.Operator):
    """Compensate weights by distributing unused weights to used bones"""
    bl_idname = "pureq.compensate_weights"
    bl_label = "Compensate Weights"
    bl_description = "Distribute weights from unused bones to nearby used bones"
    bl_options = {'REGISTER', 'UNDO'}

    compensation_method: EnumProperty(
        name="Method",
        description="Method to use for weight compensation",
        items=[
            ('DISTRIBUTE_TO_USED', "Distribute to Used Bones", "Distribute unused bone weights to nearby used bones"),
            ('MERGE_WITH_PARENT', "Merge with Parent", "Merge unused bones with their parent bones"),
            ('REDISTRIBUTE_UNIFORM', "Redistribute Uniformly", "Redistribute weights uniformly among used bones"),
        ],
        default='DISTRIBUTE_TO_USED'
    )

    threshold: FloatProperty(
        name="Unused Threshold",
        description="Bones with total weight below this threshold are considered unused",
        default=0.01,
        min=0.0,
        max=1.0
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        # Find unused vertex groups (those with very low total weights)
        unused_groups = []
        used_groups = []

        for vg in obj.vertex_groups:
            total_weight = 0
            for v in obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index:
                        total_weight += g.weight
                        if total_weight > self.threshold:  # Early exit if we exceed threshold
                            break
            if total_weight <= self.threshold:
                unused_groups.append(vg)
            else:
                used_groups.append(vg)

        if not unused_groups:
            self.report({'INFO'}, "No unused vertex groups found")
            return {'FINISHED'}

        if self.compensation_method == 'DISTRIBUTE_TO_USED':
            # Distribute weights from unused groups to nearby used groups
            redistributed_count = 0
            for unused_vg in unused_groups:
                # For each vertex in the unused group, try to add its weight to nearby used groups
                for v in obj.data.vertices:
                    for g in v.groups:
                        if g.group == unused_vg.index:
                            weight_to_redistribute = g.weight
                            # Find the best used group for this vertex
                            best_used_group = None
                            best_distance = float('inf')

                            # For now, we'll just add to the first used group found for this vertex
                            for g2 in v.groups:
                                vg2 = obj.vertex_groups[g2.group]
                                if vg2 in used_groups and vg2 != unused_vg:
                                    # Add the weight to this used group
                                    vg2.add([v.index], weight_to_redistribute, 'ADD')
                                    break
                            else:
                                # If no used group found, try to find a nearby one based on position
                                # This is a simplified approach - a more sophisticated one would use bone hierarchy
                                if used_groups:
                                    # Add to the first available used group
                                    used_groups[0].add([v.index], weight_to_redistribute, 'ADD')

                            # Remove the weight from the unused group
                            unused_vg.remove([v.index])
                            redistributed_count += 1
                            break  # Move to next vertex after redistributing one weight

        elif self.compensation_method == 'MERGE_WITH_PARENT':
            # In a more advanced implementation, we would merge with parent bones based on armature hierarchy
            # For now, we'll simulate this by merging with similar named bones
            armature_modifier = None
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE':
                    armature_modifier = mod
                    break

            if armature_modifier and armature_modifier.object:
                armature = armature_modifier.object
                # This would require more complex logic to identify parent-child bone relationships
                self.report({'INFO'}, f"Parent merge not fully implemented, would merge {len(unused_groups)} groups with parents")

        elif self.compensation_method == 'REDISTRIBUTE_UNIFORM':
            # Redistribute weights uniformly among all used bones for vertices that had unused bone weights
            for v in obj.data.vertices:
                redistribute_total = 0
                redistribute_groups = []

                # Check if this vertex has weights from unused groups
                for g in v.groups:
                    vg = obj.vertex_groups[g.group]
                    if vg in unused_groups:
                        redistribute_total += g.weight
                        redistribute_groups.append(g.group)

                if redistribute_total > 0 and len(used_groups) > 0:
                    # Distribute the total unused weight among used groups
                    weight_per_used = redistribute_total / len(used_groups)
                    for used_vg in used_groups:
                        used_vg.add([v.index], weight_per_used, 'ADD')

                    # Remove weights from unused groups
                    for vg_idx in redistribute_groups:
                        vg = obj.vertex_groups[vg_idx]
                        vg.remove([v.index])

        self.report({'INFO'}, f"Compensated weights: {len(unused_groups)} unused groups processed")

        # Normalize weights after compensation
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)

        return {'FINISHED'}


class PureQ_OT_identify_unused_bones(bpy.types.Operator):
    """Identify and list unused bones in the vertex groups"""
    bl_idname = "pureq.identify_unused_bones"
    bl_label = "Identify Unused Bones"
    bl_description = "Identify and list vertex groups with very low total weights"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Unused Threshold",
        description="Bones with total weight below this threshold are considered unused",
        default=0.01,
        min=0.0,
        max=1.0
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        unused_groups = []
        used_groups = []

        for vg in obj.vertex_groups:
            total_weight = 0
            for v in obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index:
                        total_weight += g.weight
                        # Early exit if we know it's above threshold
                        if total_weight > self.threshold:
                            break
            if total_weight <= self.threshold:
                unused_groups.append((vg.name, total_weight))
            else:
                used_groups.append((vg.name, total_weight))

        # Print results to console
        print("\n--- Vertex Group Analysis ---")
        print(f"Used Groups ({len(used_groups)}):")
        for name, weight in sorted(used_groups, key=lambda x: x[1], reverse=True):
            print(f"  {name}: {weight:.4f}")

        print(f"\nUnused Groups ({len(unused_groups)}):")
        for name, weight in sorted(unused_groups, key=lambda x: x[1], reverse=True):
            print(f"  {name}: {weight:.4f}")

        self.report({'INFO'}, f"Analysis complete: {len(used_groups)} used, {len(unused_groups)} unused vertex groups")

        return {'FINISHED'}


class PureQ_OT_smooth_clean_weights(bpy.types.Operator):
    """Normalize, Smooth and Clean weights in one pass"""
    bl_idname = "pureq.smooth_clean_weights"
    bl_label = "Smooth & Clean Weights"
    bl_description = "Normalize, Smooth and Clean weights to improve fold quality"
    bl_options = {'REGISTER', 'UNDO'}

    iterations: bpy.props.IntProperty(name="Iterations", default=2, min=1, max=20)
    smooth_factor: bpy.props.FloatProperty(name="Smooth Factor", default=0.5, min=0.0, max=1.0)
    clean_threshold: bpy.props.FloatProperty(name="Clean Threshold", default=0.001, min=0.0, max=1.0)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        # Store mode
        prev_mode = obj.mode
        if prev_mode != 'WEIGHT_PAINT':
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        try:
            # 1. Initial Normalize
            bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)

            # 2. Smooth Loop
            for i in range(self.iterations):
                for vg in obj.vertex_groups:
                    bpy.ops.object.vertex_group_set_active(group=vg.name)
                    bpy.ops.object.vertex_group_smooth(factor=self.smooth_factor, repeat=1)

                # Normalize after each pass
                bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)

            # 3. Clean
            bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=self.clean_threshold)

            # 4. Final Normalize
            bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)

        finally:
            if prev_mode != 'WEIGHT_PAINT':
                bpy.ops.object.mode_set(mode=prev_mode)

        self.report({'INFO'}, "Weights Smoothed and Cleaned")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(PureQ_OT_auto_clean_vertex_groups)
    bpy.utils.register_class(PureQ_OT_select_low_weight_vertices)
    bpy.utils.register_class(PureQ_OT_merge_similar_vertex_groups)
    bpy.utils.register_class(PureQ_OT_compensate_weights)
    bpy.utils.register_class(PureQ_OT_identify_unused_bones)
    bpy.utils.register_class(PureQ_OT_smooth_clean_weights)


def unregister():
    bpy.utils.unregister_class(PureQ_OT_auto_clean_vertex_groups)
    bpy.utils.unregister_class(PureQ_OT_select_low_weight_vertices)
    bpy.utils.unregister_class(PureQ_OT_merge_similar_vertex_groups)
    bpy.utils.unregister_class(PureQ_OT_compensate_weights)
    bpy.utils.unregister_class(PureQ_OT_identify_unused_bones)
    bpy.utils.unregister_class(PureQ_OT_smooth_clean_weights)

