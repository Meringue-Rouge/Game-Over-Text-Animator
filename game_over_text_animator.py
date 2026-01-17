bl_info = {
    "name": "Game Over Text Animator",
    "author": "Grok",
    "version": (1, 7, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Text Animator",
    "description": "Creates rigged 3D text with per-letter animations using a single armature",
    "category": "Animation",
}

import bpy
import random
from bpy.types import Operator, Panel
from math import radians, sin, cos, pi
import bpy_extras.anim_utils as anim_utils

class TEXT_ANIM_OT_run(Operator):
    bl_idname = "object.text_anim_run"
    bl_label = "Create Animated Text"
    bl_description = "Creates rigged 3D text with per-letter appear animation"
    bl_options = {'REGISTER', 'UNDO'}

    def get_char_width(self, c, context, font, extrude, bevel_depth, bevel_res, res_u):
        curve_data = bpy.data.curves.new("Temp_Curve", 'FONT')
        if font:
            curve_data.font = font
        curve_data.body = c
        curve_data.align_x = 'CENTER'
        curve_data.extrude = extrude
        curve_data.bevel_depth = bevel_depth
        curve_data.bevel_resolution = bevel_res
        curve_data.resolution_u = res_u
        
        temp_obj = bpy.data.objects.new("Temp_Obj", curve_data)
        context.collection.objects.link(temp_obj)
        context.view_layer.update()
        width = temp_obj.dimensions.x
        
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        bpy.data.curves.remove(curve_data, do_unlink=True)
        return width

    def execute(self, context):
        text = context.scene.text_anim_input.upper()
        extra_spacing = context.scene.text_anim_spacing
        font_path = context.scene.text_anim_font
        try:
            font = bpy.data.fonts.load(font_path) if font_path else None
        except:
            font = None
            
        anim_type = context.scene.text_anim_type
        extrude = 0.05
        bevel_depth = 0.02
        bevel_res = 5
        res_u = 12

        context.scene.render.fps = 60
        context.scene.render.fps_base = 1

        # --- 1. Calculate Positions ---
        chars = list(text)
        letter_chars = [c for c in chars if not c.isspace()]
        positions = []
        current_x = 0.0
        
        for c in chars:
            width = self.get_char_width(c, context, font, extrude, bevel_depth, bevel_res, res_u)
            if not c.isspace():
                positions.append(current_x + width / 2)
            current_x += width + extra_spacing
            
        total_width = current_x - extra_spacing
        start_x = -total_width / 2
        positions = [start_x + p for p in positions]

        # --- Material Setup ---
        mat_name = "GameOver_Text_Mat"
        common_mat = bpy.data.materials.get(mat_name)
        if not common_mat:
            common_mat = bpy.data.materials.new(name=mat_name)
            common_mat.use_nodes = True

        # --- 2. Create Objects ---
        letter_objs = []
        bpy.ops.object.select_all(action='DESELECT')

        for i, c in enumerate(letter_chars):
            curve = bpy.data.curves.new(name=f"Char_{i}", type='FONT')
            if font:
                curve.font = font
            curve.body = c
            curve.align_x = 'CENTER'
            curve.extrude = extrude
            curve.bevel_depth = bevel_depth
            curve.bevel_resolution = bevel_res
            curve.resolution_u = res_u
            
            letter_obj = bpy.data.objects.new(f"Letter_{i}", curve)
            context.collection.objects.link(letter_obj)
            letter_obj.location = (positions[i], 0, 0)
            letter_obj.rotation_euler = (radians(90), 0, 0)
            
            # Assign Material
            letter_obj.data.materials.append(common_mat)
            
            letter_obj.select_set(True)
            context.view_layer.objects.active = letter_obj
            bpy.ops.object.convert(target='MESH')
            
            # Decimate Modifier
            dec_mod = letter_obj.modifiers.new(name="Decimate", type='DECIMATE')
            dec_mod.ratio = 0.1
            dec_mod.decimate_type = 'COLLAPSE'
            dec_mod.use_collapse_triangulate = True
            
            letter_objs.append(letter_obj)
            bpy.ops.object.select_all(action='DESELECT')

        # --- 3. Create Armature ---
        armature = bpy.data.armatures.new("TextArmature")
        arm_obj = bpy.data.objects.new("TextArmature", armature)
        context.collection.objects.link(arm_obj)
        context.view_layer.objects.active = arm_obj
        
        bpy.ops.object.mode_set(mode='EDIT')
        for i in range(len(letter_objs)):
            ebone = armature.edit_bones.new(f"Bone_{i}")
            ebone.head = (positions[i], 0, 0)
            ebone.tail = (positions[i], 0, 0.05)
        bpy.ops.object.mode_set(mode='OBJECT')

        # --- 4. Rigging ---
        for i, letter in enumerate(letter_objs):
            bpy.ops.object.select_all(action='DESELECT')
            letter.select_set(True)
            context.view_layer.objects.active = letter
            
            context.view_layer.update()
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
            
            min_x = min(v.co.x for v in letter.data.vertices)
            max_x = max(v.co.x for v in letter.data.vertices)
            min_y = min(v.co.y for v in letter.data.vertices)
            max_y = max(v.co.y for v in letter.data.vertices)
            min_z = min(v.co.z for v in letter.data.vertices)
            max_z = max(v.co.z for v in letter.data.vertices)
            
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            height = max_z - min_z
            center_z = height / 2

            for v in letter.data.vertices:
                v.co.x -= center_x
                v.co.y -= center_y
                v.co.z -= min_z 
            for v in letter.data.vertices:
                v.co.z -= center_z

            letter.location = (positions[i], 0, 0)

            mod = letter.modifiers.new("Armature", 'ARMATURE')
            mod.object = arm_obj
            vgroup = letter.vertex_groups.new(name=f"Bone_{i}")
            vgroup.add([v.index for v in letter.data.vertices], 1.0, 'REPLACE')

            context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='EDIT')
            bone_name = f"Bone_{i}"
            if bone_name in armature.edit_bones:
                ebone = armature.edit_bones[bone_name]
                ebone.head.z = center_z
                ebone.tail.z = center_z + 0.05
            bpy.ops.object.mode_set(mode='OBJECT')

        # --- 5. Animation ---
        bones = [arm_obj.pose.bones[f"Bone_{i}"] for i in range(len(letter_objs))]

        empty = bpy.data.objects.new("GameOver_Text_Group", None)
        context.collection.objects.link(empty)
        empty.location = (0, 0, 0)
        arm_obj.parent = empty

        num_letters = len(bones)
        interval = 15
        appear_start_base = 1
        frame_end = 1

        if anim_type == 'DAYTONA':
            appear_dur = 10
            shuffle_start_base = appear_start_base + 5
            shuffle_dur = 40
            rotation_start_base = shuffle_start_base + 20
            hold_dur = 60
            transition_dur = 8
            num_snaps = 4
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                appear_start = appear_start_base + idx * 4 
                bone.scale = (0.001, 0.001, 0.001)
                bone.keyframe_insert(data_path="scale", frame=appear_start)
                bone.scale = (1.2, 1.2, 1.2)
                bone.keyframe_insert(data_path="scale", frame=appear_start + appear_dur * 0.6)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=appear_start + appear_dur)
                shuffle_start = appear_start + appear_dur
                num_shuffles = 6
                shuffle_step = shuffle_dur / num_shuffles
                for s in range(num_shuffles):
                    t = s / num_shuffles
                    frame = shuffle_start + s * shuffle_step
                    direction = 1 if s % 2 == 0 else -1
                    mag = 0.3 * (1 - t)
                    bone.location.x = direction * mag
                    bone.keyframe_insert(data_path="location", index=0, frame=frame)
                    bone.location.z = abs(mag) * 0.5
                    bone.keyframe_insert(data_path="location", index=2, frame=frame)
                bone.location.x = 0
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", frame=shuffle_start + shuffle_dur)
                rot_start = rotation_start_base + idx * 12
                frame = rot_start
                current_rot = 0.0
                bone.rotation_euler[2] = radians(current_rot)
                bone.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
                frame += hold_dur
                bone.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
                for i in range(num_snaps):
                    trans_end = frame + transition_dur
                    current_rot += 90
                    bone.rotation_euler[2] = radians(current_rot)
                    bone.keyframe_insert(data_path="rotation_euler", index=2, frame=trans_end)
                    hold_end = trans_end + hold_dur
                    bone.keyframe_insert(data_path="rotation_euler", index=2, frame=hold_end)
                    frame = hold_end
                if frame > frame_end: frame_end = frame

        elif anim_type == 'CIRCULAR_APPROACH':
            approach_dur = 120
            circle_radius = 2.0
            num_circles = 2
            self_rot_speed = 360
            zig_zag_amp = 1.0
            zig_zag_freq = 4
            spin_jump_dur = 30
            spin_jump_delay = 5
            spin_jump_height = 1.0
            approach_end_base = appear_start_base + (num_letters - 1) * (approach_dur // 2) + approach_dur
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                appear_start = appear_start_base + idx * (approach_dur // 2)
                bone.scale = (0.001, 0.001, 0.001)
                bone.keyframe_insert(data_path="scale", frame=appear_start - 1)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=appear_start)
                bone.rotation_euler[2] = 0
                bone.keyframe_insert(data_path="rotation_euler", index=2, frame=appear_start - 1)
                bone.keyframe_insert(data_path="rotation_euler", index=2, frame=appear_start)
                num_steps = 40
                start_y = -20.0
                for step in range(num_steps + 1):
                    t = step / num_steps
                    frame = appear_start + int(t * approach_dur)
                    base_y = start_y + t * (0 - start_y)
                    zig_y = zig_zag_amp * sin(t * 2 * pi * zig_zag_freq) * (1 - t)
                    y = base_y + zig_y
                    angle = t * 2 * pi * num_circles
                    x_offset = circle_radius * sin(angle) * (1 - t)
                    z_offset = circle_radius * cos(angle) * (1 - t)
                    bone.location = (x_offset, y, z_offset)
                    bone.keyframe_insert(data_path="location", frame=frame)
                    self_rot = t * self_rot_speed
                    bone.rotation_euler[2] = radians(self_rot)
                    bone.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
                bone.location = (0, 0, 0)
                bone.keyframe_insert(data_path="location", frame=appear_start + approach_dur)
                bone.rotation_euler[2] = radians(self_rot_speed % 360)
                bone.keyframe_insert(data_path="rotation_euler", index=2, frame=appear_start + approach_dur)
                if arm_obj.animation_data and arm_obj.animation_data.action:
                    action = arm_obj.animation_data.action
                    if hasattr(action, 'fcurves'):
                        for fc in action.fcurves:
                             if "rotation_euler" in fc.data_path and fc.array_index == 2:
                                for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
                jump_start = approach_end_base + idx * spin_jump_delay
                bone.scale = (1.2, 1.2, 0.8)
                bone.keyframe_insert(data_path="scale", frame=jump_start)
                mid_jump = jump_start + spin_jump_dur // 2
                bone.location.z = spin_jump_height
                bone.keyframe_insert(data_path="location", index=2, frame=mid_jump)
                bone.rotation_euler[2] += radians(360)
                bone.keyframe_insert(data_path="rotation_euler", index=2, frame=mid_jump)
                bone.scale = (0.8, 0.8, 1.2)
                bone.keyframe_insert(data_path="scale", frame=mid_jump)
                end_jump = jump_start + spin_jump_dur
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=end_jump)
                bone.scale = (1.2, 1.2, 0.8)
                bone.keyframe_insert(data_path="scale", frame=end_jump)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=end_jump + 5)
                end_frame = end_jump + 5
                if end_frame > frame_end: frame_end = end_frame

        elif anim_type == 'BAD_GAME_OVER':
            drop_dur = 30
            bounce_dur = 15
            fall_dur = 20
            free_fall_dur = 30 # New duration for free fall out of scene
            drop_height = 5.0
            
            # Base frame calculation
            fall_start_base = appear_start_base + num_letters * interval + drop_dur + bounce_dur + 20
            
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                appear_start = appear_start_base + idx * interval
                
                # --- Phase 1: Drop and Bounce (Unchanged) ---
                bone.location.z = drop_height
                bone.keyframe_insert(data_path="location", index=2, frame=appear_start)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=appear_start)
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=appear_start)
                land = appear_start + drop_dur
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=land)
                squash = land
                bone.scale = (1.2, 1.2, 0.8)
                bone.keyframe_insert(data_path="scale", frame=squash)
                bounce_peak = land + bounce_dur // 2
                bone.location.z = 0.5
                bone.keyframe_insert(data_path="location", index=2, frame=bounce_peak)
                bone.scale = (0.8, 0.8, 1.2)
                bone.keyframe_insert(data_path="scale", frame=bounce_peak)
                bounce_end = land + bounce_dur
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=bounce_end)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=bounce_end)
                
                # --- Phase 2: Flat Flip ---
                fall_start = fall_start_base + idx * 5
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=fall_start)
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=fall_start)
                
                fall_end = fall_start + fall_dur
                # Change to 180 degrees for a flat, face-down flip
                bone.rotation_euler = (radians(180), 0, 0) 
                bone.keyframe_insert(data_path="rotation_euler", frame=fall_end)
                
                # Scale for effect after flip
                bone.scale = (1.1, 1.1, 0.9)
                bone.keyframe_insert(data_path="scale", frame=fall_end)

                # --- Phase 3: Free Fall ---
                # Key the final flip position and scale
                bone.location.z = 0 
                bone.keyframe_insert(data_path="location", index=2, frame=fall_end)

                free_fall_end = fall_end + free_fall_dur
                
                # Free fall motion
                bone.location.z = -10.0 
                bone.keyframe_insert(data_path="location", index=2, frame=free_fall_end)

                # Scale returns to normal while falling
                bone.scale = (1.0, 1.0, 1.0)
                bone.keyframe_insert(data_path="scale", frame=free_fall_end) 

                end_frame = free_fall_end
                if end_frame > frame_end: frame_end = end_frame

        elif anim_type == 'GOOD_GAME_OVER':
            rise_dur = 60
            spiral_dur = 60
            dance_dur = 30
            delay_between_dances = 30
            assemble_base = appear_start_base + num_letters * interval + rise_dur + spiral_dur + 20
            second_dance_start_base = assemble_base + dance_dur + delay_between_dances
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                appear_start = appear_start_base + idx * interval
                bone.location.z = -5.0
                bone.keyframe_insert(data_path="location", index=2, frame=appear_start)
                bone.scale = (0.5, 0.5, 0.5)
                bone.keyframe_insert(data_path="scale", frame=appear_start)
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=appear_start)
                rise_end = appear_start + rise_dur
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=rise_end)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=rise_end)
                spiral_start = rise_end
                num_spiral_steps = 20
                for step in range(num_spiral_steps + 1):
                    t = step / num_spiral_steps
                    frame = spiral_start + int(t * spiral_dur)
                    angle = t * 2 * pi * 2
                    x_offset = 0.5 * cos(angle) * (1 - t)
                    y_offset = 0.5 * sin(angle) * (1 - t)
                    bone.location = (x_offset, y_offset, 0)
                    bone.keyframe_insert(data_path="location", frame=frame)
                    rot_x = t * 360
                    rot_y = t * 180
                    rot_z = t * 720
                    bone.rotation_euler = (radians(rot_x), radians(rot_y), radians(rot_z))
                    bone.keyframe_insert(data_path="rotation_euler", frame=frame)
                spiral_end = spiral_start + spiral_dur
                bone.location = (0, 0, 0)
                bone.keyframe_insert(data_path="location", frame=spiral_end)
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=spiral_end)
                dance_start = assemble_base + idx * 5
                bone.scale = (1.1, 1.1, 1.1)
                bone.keyframe_insert(data_path="scale", frame=dance_start)
                bone.rotation_euler = (radians(5), radians(5), radians(10))
                bone.keyframe_insert(data_path="rotation_euler", frame=dance_start)
                dance_mid = dance_start + dance_dur // 2
                bone.scale = (0.9, 0.9, 0.9)
                bone.keyframe_insert(data_path="scale", frame=dance_mid)
                bone.rotation_euler = (radians(-5), radians(-5), radians(-10))
                bone.keyframe_insert(data_path="rotation_euler", frame=dance_mid)
                dance_end = dance_start + dance_dur
                bone.scale = (1.1, 1.1, 1.1)
                bone.keyframe_insert(data_path="scale", frame=dance_end)
                bone.rotation_euler = (radians(5), radians(5), radians(10))
                bone.keyframe_insert(data_path="rotation_euler", frame=dance_end)
                second_dance_start = second_dance_start_base + idx * 5
                bone.scale = (1.1, 1.1, 1.1)
                bone.keyframe_insert(data_path="scale", frame=second_dance_start)
                bone.rotation_euler = (radians(-5), radians(-5), radians(-10))
                bone.keyframe_insert(data_path="rotation_euler", frame=second_dance_start)
                second_dance_mid = second_dance_start + dance_dur // 2
                bone.scale = (0.9, 0.9, 0.9)
                bone.keyframe_insert(data_path="scale", frame=second_dance_mid)
                bone.rotation_euler = (radians(5), radians(5), radians(10))
                bone.keyframe_insert(data_path="rotation_euler", frame=second_dance_mid)
                second_dance_end = second_dance_start + dance_dur
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=second_dance_end)
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=second_dance_end)
                end_frame = second_dance_end
                if end_frame > frame_end: frame_end = end_frame
        
        elif anim_type == 'ELASTIC_WAVE':
            wave_interval = 10
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                start_frame = appear_start_base + idx * wave_interval
                bone.scale = (0, 0, 0)
                bone.keyframe_insert(data_path="scale", frame=start_frame)
                stretch_frame = start_frame + 10
                bone.scale = (0.6, 0.6, 2.0)
                bone.keyframe_insert(data_path="scale", frame=stretch_frame)
                squash_frame = start_frame + 20
                bone.scale = (1.5, 1.5, 0.5)
                bone.keyframe_insert(data_path="scale", frame=squash_frame)
                settle_1 = start_frame + 28
                bone.scale = (0.9, 0.9, 1.1)
                bone.keyframe_insert(data_path="scale", frame=settle_1)
                settle_2 = start_frame + 35
                bone.scale = (1.0, 1.0, 1.0)
                bone.keyframe_insert(data_path="scale", frame=settle_2)
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=start_frame)
                bone.location.z = 1.0
                bone.keyframe_insert(data_path="location", index=2, frame=stretch_frame)
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=squash_frame)
                if settle_2 > frame_end: frame_end = settle_2

        elif anim_type == '3D_TUMBLE':
            tumble_dur = 60
            interval = 10
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                start_frame = appear_start_base + idx * interval
                bone.scale = (0, 0, 0)
                bone.keyframe_insert(data_path="scale", frame=start_frame)
                rot_x = 2 * pi * 2 
                rot_y = 2 * pi * 1.5 if idx % 2 == 0 else -2 * pi * 1.5
                bone.rotation_euler = (rot_x, rot_y, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=start_frame)
                mid_frame = start_frame + tumble_dur // 2
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=mid_frame)
                end_frame_anim = start_frame + tumble_dur
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=end_frame_anim)
                kick_frame = end_frame_anim + 5
                bone.rotation_euler = (radians(-10), 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=kick_frame)
                settle_frame = end_frame_anim + 15
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=settle_frame)
                if settle_frame > frame_end: frame_end = settle_frame

        elif anim_type == 'DIGITAL_GLITCH':
            fall_dur = 20
            glitch_dur = 30
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                appear_start = appear_start_base + idx * 5
                bone.location.z = 10.0
                bone.keyframe_insert(data_path="location", index=2, frame=appear_start)
                bone.scale = (0.5, 0.5, 3.0)
                bone.keyframe_insert(data_path="scale", frame=appear_start)
                impact_frame = appear_start + fall_dur
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=impact_frame)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=impact_frame)
                current_f = impact_frame
                end_glitch = impact_frame + glitch_dur
                while current_f < end_glitch:
                    current_f += random.randint(2, 4)
                    rx = random.uniform(-0.2, 0.2)
                    rz = random.uniform(-0.2, 0.2)
                    sx = random.uniform(0.8, 1.2)
                    sy = random.uniform(0.8, 1.2)
                    bone.location.x = rx
                    bone.location.z = rz
                    bone.scale = (sx, sy, 1)
                    bone.keyframe_insert(data_path="location", frame=current_f)
                    bone.keyframe_insert(data_path="scale", frame=current_f)
                final_frame = end_glitch + 5
                bone.location = (0, 0, 0)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="location", frame=final_frame)
                bone.keyframe_insert(data_path="scale", frame=final_frame)
                if final_frame > frame_end: frame_end = final_frame

        elif anim_type == 'SLINGSHOT_SNAP':
            tension_dur = 40
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                start_t = appear_start_base + idx * 5
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=start_t)
                bone.scale = (1, 1, 1)
                bone.keyframe_insert(data_path="scale", frame=start_t)
                release_t = start_t + tension_dur
                bone.location.z = -5.0 
                bone.keyframe_insert(data_path="location", index=2, frame=release_t)
                bone.rotation_euler = (radians(random.uniform(-5, 5)), radians(random.uniform(-5, 5)), 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=release_t)
                snap_t = release_t + 4 
                bone.location.z = 2.0 
                bone.keyframe_insert(data_path="location", index=2, frame=snap_t)
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=snap_t)
                settle_1 = snap_t + 8
                bone.location.z = -0.5
                bone.keyframe_insert(data_path="location", index=2, frame=settle_1)
                settle_2 = snap_t + 14
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=settle_2)
                if settle_2 > frame_end: frame_end = settle_2

        elif anim_type == 'ARCADE_SLAM':
            slam_dur = 10
            recoil_dur = 8
            jitter_dur = 30
            for idx, bone in enumerate(bones):
                bone.rotation_mode = 'XYZ'
                start_frame = appear_start_base + idx * 2
                bone.location.z = -40.0
                bone.keyframe_insert(data_path="location", index=2, frame=start_frame)
                bone.scale = (0.1, 0.1, 0.1)
                bone.keyframe_insert(data_path="scale", frame=start_frame)
                rx = radians(random.uniform(-720, 720))
                ry = radians(random.uniform(-720, 720))
                rz = radians(random.uniform(-720, 720))
                bone.rotation_euler = (rx, ry, rz)
                bone.keyframe_insert(data_path="rotation_euler", frame=start_frame)
                impact_frame = start_frame + slam_dur
                bone.location.z = 0
                bone.keyframe_insert(data_path="location", index=2, frame=impact_frame)
                bone.rotation_euler = (0, 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=impact_frame)
                bone.scale = (2.0, 2.0, 2.0) 
                bone.keyframe_insert(data_path="scale", frame=impact_frame)
                recoil_frame = impact_frame + 4
                bone.scale = (0.8, 0.8, 0.8) 
                bone.keyframe_insert(data_path="scale", frame=recoil_frame)
                settle_frame = recoil_frame + 4
                bone.scale = (1.0, 1.0, 1.0)
                bone.keyframe_insert(data_path="scale", frame=settle_frame)
                jitter_end = settle_frame + jitter_dur
                cur_j = settle_frame
                while cur_j < jitter_end:
                    cur_j += 2
                    jx = random.uniform(-0.1, 0.1)
                    jz = random.uniform(-0.1, 0.1)
                    bone.location.x = jx
                    bone.location.z = jz
                    bone.keyframe_insert(data_path="location", frame=cur_j)
                bone.location = (0, 0, 0)
                bone.keyframe_insert(data_path="location", frame=jitter_end)
                pulse_start = jitter_end
                pulse_period = 20
                for p in range(3):
                    base = pulse_start + p * pulse_period
                    peak = base + 5
                    end = base + 10
                    bone.scale = (1.0, 1.0, 1.0)
                    bone.keyframe_insert(data_path="scale", frame=base)
                    bone.scale = (1.15, 1.15, 1.15)
                    bone.keyframe_insert(data_path="scale", frame=peak)
                    bone.scale = (1.0, 1.0, 1.0)
                    bone.keyframe_insert(data_path="scale", frame=end)
                    frame_end = end


        context.scene.frame_end = frame_end + 50
        context.scene.frame_current = 1
        bpy.ops.object.select_all(action='DESELECT')
        empty.select_set(True)
        context.view_layer.objects.active = empty
        self.report({'INFO'}, f"Created animated text: {text} with {anim_type} animation")
        return {'FINISHED'}

class TEXT_ANIM_PT_panel(Panel):
    bl_label = "Game Over Text Animator"
    bl_idname = "TEXT_ANIM_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Text Animator"
    bl_context = "objectmode"
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "text_anim_input", text="Text")
        layout.prop(context.scene, "text_anim_font", text="Font File")
        layout.prop(context.scene, "text_anim_spacing", text="Spacing")
        layout.prop(context.scene, "text_anim_type", text="Animation Type")
        layout.operator("object.text_anim_run", text="Run Animation", icon='PLAY')

def register_properties():
    bpy.types.Scene.text_anim_input = bpy.props.StringProperty(name="Text", description="Text to animate", default="GAME OVER!")
    bpy.types.Scene.text_anim_font = bpy.props.StringProperty(name="Font File", description="Path to font file", subtype='FILE_PATH', default="")
    bpy.types.Scene.text_anim_spacing = bpy.props.FloatProperty(name="Spacing", description="Extra spacing", default=0.0, min=0.0)
    bpy.types.Scene.text_anim_type = bpy.props.EnumProperty(
        items=[
            ('DAYTONA', "Daytona USA-like", "Shuffle and Snap"),
            ('CIRCULAR_APPROACH', "Circular Approach", ""),
            ('BAD_GAME_OVER', "Bad Game Over", ""),
            ('GOOD_GAME_OVER', "Good Game Over", ""),
            ('ELASTIC_WAVE', "Elastic Wave", ""),
            ('3D_TUMBLE', "3D Tumble", ""),
            ('DIGITAL_GLITCH', "Digital Glitch", "Phase 1: Fall, Phase 2: Glitch"),
            ('SLINGSHOT_SNAP', "Slingshot Snap", "Phase 1: Tension, Phase 2: Release"),
            ('ARCADE_SLAM', "Arcade Slam", "Phase 1: Meteor, Phase 2: Impact, Phase 3: Pulse")
        ],
        name="Animation Type",
        default='DAYTONA'
    )

def unregister_properties():
    del bpy.types.Scene.text_anim_input
    del bpy.types.Scene.text_anim_font
    del bpy.types.Scene.text_anim_spacing
    del bpy.types.Scene.text_anim_type

classes = (TEXT_ANIM_OT_run, TEXT_ANIM_PT_panel)
def register():
    register_properties()
    for cls in classes: bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
    unregister_properties()
if __name__ == "__main__": register()