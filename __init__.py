import bpy
from bpy.props import FloatVectorProperty, CollectionProperty, PointerProperty, IntProperty, BoolProperty, StringProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup

class ColorPaletteItem(PropertyGroup):
    color_start: FloatVectorProperty(name="Start Color", subtype='COLOR', default=(1.0, 1.0, 1.0), min=0.0, max=1.0)
    color_end: FloatVectorProperty(name="End Color", subtype='COLOR', default=(1.0, 1.0, 1.0), min=0.0, max=1.0)

class ColorPaletteSettings(PropertyGroup):
    colors: CollectionProperty(type=ColorPaletteItem)
    color_block_size: IntProperty(name="Color Block Size", default=128, min=1)
    cols: IntProperty(name="Columns", default=4, min=1)
    rows: IntProperty(name="Rows", default=4, min=1)
    create_new: BoolProperty(name="Create New Texture", default=True)
    texture_name: StringProperty(name="Texture Name", default="ColorGridTexture")
    gradient_mode: BoolProperty(name="Gradient Mode", default=False)
    gradient_orientation: EnumProperty(name="Gradient Orientation", default="VERTICAL", items=[("VERTICAL", "Vertical", "Gradient flows vertically"), ("HORIZONTAL", "Horizontal", "Gradient flows horizontally")])

class ColorGridTextureGeneratorPanel(Panel):
    bl_label = "Color Grid Texture Generator"
    bl_idname = "IMAGE_PT_color_grid"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Color Grid"

    def draw(self, context):
        layout = self.layout
        if not layout:
            return
        settings = context.scene.color_palette_settings

        # Button to update palette from Coolors URL
        layout.operator("texture.update_palette_from_coolors", text="Update Palette from Coolors URL", icon='PASTEDOWN')

        # Load settings from the active image if it contains color_grid metadata
        active_image = context.area.spaces.active.image if context.area.spaces.active.type == 'IMAGE_EDITOR' else None
        if active_image and isinstance(active_image.get('color_grid'), dict):
            metadata = active_image['color_grid']
            settings.cols = metadata.get("cols", settings.cols)
            settings.rows = metadata.get("rows", settings.rows)
            settings.color_block_size = metadata.get("color_block_size", settings.color_block_size)
            settings.gradient_mode = metadata.get("gradient_mode", settings.gradient_mode)
            settings.gradient_orientation = metadata.get("gradient_orientation", settings.gradient_orientation)

        # Color Palette Section
        layout.label(text="Color Palette:")
        box = layout.box()
        for index, item in enumerate(settings.colors):
            row = box.row()
            if settings.gradient_mode:
                row.prop(item, "color_start", text="")
                row.prop(item, "color_end", text="")
            else:
                row.prop(item, "color_start", text="")
            row.operator("texture.remove_color", text="", icon='REMOVE').index = index

        # Add Color Button
        box.operator("texture.add_color", text="Add Color", icon='ADD')

        # Texture Settings Section
        layout.label(text="Texture Settings:")
        box = layout.box()
        box.prop(settings, "color_block_size", text="Block Size")
        box.prop(settings, "cols", text="Columns")
        box.prop(settings, "rows", text="Rows")
        box.prop(settings, "create_new", text="Create New Texture")

        # Gradient Settings Section
        layout.label(text="Gradient Settings:")
        box = layout.box()
        box.prop(settings, "gradient_mode", text="Enable Gradient Mode")
        if settings.gradient_mode:
            box.prop(settings, "gradient_orientation", text="Orientation")

        # Generate Texture Button
        layout.operator("texture.generate_texture", text="Generate Texture", icon='TEXTURE')

class AddColorOperator(Operator):
    bl_idname = "texture.add_color"
    bl_label = "Add Color"

    def execute(self, context):
        settings = context.scene.color_palette_settings
        settings.colors.add()
        return {'FINISHED'}

class RemoveColorOperator(Operator):
    bl_idname = "texture.remove_color"
    bl_label = "Remove Color"

    index: bpy.props.IntProperty()

    def execute(self, context):
        settings = context.scene.color_palette_settings
        settings.colors.remove(self.index)
        return {'FINISHED'}

class GenerateTextureOperator(Operator):
    bl_idname = "texture.generate_texture"
    bl_label = "Generate Texture"

    def execute(self, context):
        settings = context.scene.color_palette_settings
        colors = [(gamma_correct(item.color_start), gamma_correct(item.color_end)) for item in settings.colors]

        if not colors:
            self.report({'WARNING'}, "No colors in palette")
            return {'CANCELLED'}

        # Get the active image from the image editor
        image = context.area.spaces.active.image if context.area.spaces.active.type == 'IMAGE_EDITOR' else None

        if settings.create_new:
            # Create a new image
            width = max(settings.cols * settings.color_block_size, settings.rows * settings.color_block_size)
            height = width
            image = bpy.data.images.new(settings.texture_name, width, height)
        else:
            # Check if there is an active image to update
            if image is None:
                self.report({'WARNING'}, "No valid texture to update. Ensure an image is selected in the viewer.")
                return {'CANCELLED'}

            if 'color_grid' not in image:
                self.report({'WARNING'}, "Selected image is not a color grid.")
                return {'CANCELLED'}

            # Resize existing image dimensions
            width = max(settings.cols * settings.color_block_size, settings.rows * settings.color_block_size)
            height = width
            image.scale(width, height)

        # Fill the image with a grid of colors
        pixels = [0.0] * (width * height * 4)  # RGBA
        cell_width = settings.color_block_size
        cell_height = settings.color_block_size

        for y in range(settings.rows):
            for x in range(settings.cols):
                if x + y * settings.cols < len(colors):
                    color = colors[x + y * settings.cols]
                    for i in range(cell_height):
                        for j in range(cell_width):
                            if (x * cell_width + j < width) and (y * cell_height + i < height):
                                idx = ((y * cell_height + i) * width + (x * cell_width + j)) * 4
                                if settings.gradient_mode:
                                    t = (j / cell_width) if settings.gradient_orientation == "HORIZONTAL" else (1 - i / cell_height)
                                    pixels[idx:idx + 4] = [
                                        color[0][0] * (1 - t) + color[1][0] * t,
                                        color[0][1] * (1 - t) + color[1][1] * t,
                                        color[0][2] * (1 - t) + color[1][2] * t,
                                        1.0
                                    ]
                                else:
                                    if settings.gradient_mode:
                                        t = (j / cell_width) if settings.gradient_orientation == "HORIZONTAL" else (i / cell_height)
                                        pixels[idx:idx + 4] = [
                                            color[0][0] * (1 - t) + color[1][0] * t,
                                            color[0][1] * (1 - t) + color[1][1] * t,
                                            color[0][2] * (1 - t) + color[1][2] * t,
                                            1.0
                                        ]
                                    else:
                                        pixels[idx:idx + 4] = [
                                            color[0][0],
                                            color[0][1],
                                            color[0][2],
                                            1.0
                                        ]

        image.pixels = pixels
        image['color_grid'] = {
            "cols": settings.cols,
            "rows": settings.rows,
            "color_block_size": settings.color_block_size,
            "gradient_mode": settings.gradient_mode,
            "gradient_orientation": settings.gradient_orientation
        }
        image.update()

        # Switch to the new or updated texture
        context.area.spaces.active.image = image

        self.report({'INFO'}, "Texture generated: {}".format(settings.texture_name))
        return {'FINISHED'}

def gamma_correct(color):
    corrected = []
    for channel in color[:3]:  # Only apply to RGB channels
        if channel <= 0.0031308:
            corrected.append(channel * 12.92)
        else:
            corrected.append(1.055 * (channel ** (1 / 2.4)) - 0.055)
    if len(color) > 3:
        corrected.append(color[3])  # Preserve alpha channel
    return corrected

class UpdatePaletteFromCoolorsOperator(Operator):
    bl_idname = "texture.update_palette_from_coolors"
    bl_label = "Update Palette from Coolors URL"

    def execute(self, context):
        import re
        import pyperclip

        settings = context.scene.color_palette_settings
        clipboard_content = pyperclip.paste()
        coolors_pattern = r"https://coolors\.co/([0-9a-fA-F\-]+)"
        match = re.match(coolors_pattern, clipboard_content)

        if not match:
            self.report({'WARNING'}, "Clipboard does not contain a valid Coolors URL.")
            return {'CANCELLED'}

        color_hexes = match.group(1).split('-')
        settings.colors.clear()
        for hex_color in color_hexes:
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            color_item = settings.colors.add()
            color_item.color_start = (r, g, b)
            color_item.color_end = (r, g, b)

        self.report({'INFO'}, "Palette updated from Coolors URL.")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(ColorPaletteItem)
    bpy.utils.register_class(ColorPaletteSettings)
    bpy.utils.register_class(ColorGridTextureGeneratorPanel)
    bpy.utils.register_class(AddColorOperator)
    bpy.utils.register_class(RemoveColorOperator)
    bpy.utils.register_class(GenerateTextureOperator)
    bpy.utils.register_class(UpdatePaletteFromCoolorsOperator)

    bpy.types.Scene.color_palette_settings = PointerProperty(type=ColorPaletteSettings)

def unregister():
    bpy.utils.unregister_class(ColorPaletteItem)
    bpy.utils.unregister_class(ColorPaletteSettings)
    bpy.utils.unregister_class(ColorGridTextureGeneratorPanel)
    bpy.utils.unregister_class(AddColorOperator)
    bpy.utils.unregister_class(RemoveColorOperator)
    bpy.utils.unregister_class(GenerateTextureOperator)
    bpy.utils.unregister_class(UpdatePaletteFromCoolorsOperator)

    del bpy.types.Scene.color_palette_settings
