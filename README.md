
name: Blender Animation

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  render:
    runs-on: ubuntu-24.04
    timeout-minutes: 60

    steps:
      - name: Install Blender and FFmpeg
        run: |
          sudo apt-get update -qq
          sudo DEBIAN_FRONTEND=noninteractive \
            apt-get install -y \
            --no-install-recommends \
            blender ffmpeg

          blender --version
          ffmpeg -version

      - name: Create 3D scene
        run: |
          cat > scene.py <<'PY'
          import bpy
          import math

          from mathutils import Vector

          # Clear scene
          bpy.ops.object.select_all(action="SELECT")
          bpy.ops.object.delete(use_global=False)

          scene = bpy.context.scene

          # Fast CPU-compatible renderer
          scene.render.engine = "BLENDER_WORKBENCH"

          scene.display.shading.light = "STUDIO"
          scene.display.shading.color_type = "MATERIAL"
          scene.display.shading.show_shadows = True
          scene.display.shading.show_cavity = True

          # Vertical video
          scene.render.resolution_x = 360
          scene.render.resolution_y = 640
          scene.render.resolution_percentage = 100

          scene.render.fps = 24
          scene.frame_start = 1
          scene.frame_end = 24

          # Create material
          def material(name, color):
              mat = bpy.data.materials.new(name)
              mat.diffuse_color = (*color, 1.0)
              return mat

          blue = material(
              "Space Blue",
              (0.10, 0.45, 0.90)
          )

          ground_mat = material(
              "Ground",
              (0.15, 0.20, 0.30)
          )

          # Animated sphere
          bpy.ops.mesh.primitive_uv_sphere_add(
              segments=48,
              ring_count=24,
              location=(0, 0, 1)
          )

          ball = bpy.context.object
          ball.name = "Animated 3D Sphere"
          ball.data.materials.append(blue)

          bpy.ops.object.shade_smooth()

          # Actual object animation
          for frame in range(1, 25):
              t = (frame - 1) / 23

              ball.location.x = (
                  -1.0 + 2.0 * t
              )

              ball.location.z = (
                  1.0
                  + 0.5 * abs(
                      math.sin(t * math.pi * 2)
                  )
              )

              ball.rotation_euler.y = (
                  t * math.pi * 2
              )

              ball.keyframe_insert(
                  data_path="location",
                  frame=frame
              )

              ball.keyframe_insert(
                  data_path="rotation_euler",
                  frame=frame
              )

          # Ground
          bpy.ops.mesh.primitive_cube_add(
              location=(0, 0, -0.15)
          )

          ground = bpy.context.object
          ground.name = "Ground"
          ground.scale = (5, 5, 0.15)
          ground.data.materials.append(
              ground_mat
          )

          # Camera
          bpy.ops.object.camera_add(
              location=(3, -8, 3)
          )

          camera = bpy.context.object

          direction = (
              Vector((0, 0, 1))
              - camera.location
          )

          camera.rotation_euler = (
              direction.to_track_quat(
                  "-Z", "Y"
              ).to_euler()
          )

          camera.data.type = "ORTHO"
          camera.data.ortho_scale = 5

          scene.camera = camera

          # Render settings
          scene.render.image_settings.file_format = "PNG"
          scene.render.filepath = "//frames/frame_"

          # Save project
          bpy.ops.wm.save_as_mainfile(
              filepath="animation.blend"
          )

          # Render animation
          bpy.ops.render.render(animation=True)

          PY

      - name: Render frames
        run: |
          mkdir -p frames
          blender -b -t 2 --python scene.py

      - name: Create MP4
        run: |
          ffmpeg -y \
            -framerate 24 \
            -i frames/frame_%04d.png \
            -c:v libx264 \
            -preset veryfast \
            -crf 20 \
            -pix_fmt yuv420p \
            -movflags +faststart \
            animation.mp4

      - name: Verify MP4
        run: |
          test -s animation.mp4
          ffprobe -v error \
            -show_entries \
            format=duration,size \
            -of default=noprint_wrappers=1 \
            animation.mp4

      - name: Upload MP4 and project
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: blender-test-video
          path: |
            animation.mp4
            animation.blend
          retention-days: 3
