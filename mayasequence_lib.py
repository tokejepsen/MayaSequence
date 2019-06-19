import os
import shutil
import difflib
import traceback

import pymel.core as pc

from maya import mel, cmds


def render_frame(frame):

    # Set frame range.
    render_globals = pc.PyNode("defaultRenderGlobals")
    render_globals.startFrame.set(frame)
    render_globals.endFrame.set(frame)

    # Collect sequence render data.
    data = {
        "sequence_render_function": "",
        "camera": "persp",
        "width": 0,
        "height": 0,
        "save_to_render_view": ""
    }

    # Get render camera.
    for node in pc.ls(type="camera"):
        if node.renderable.get():
            data["camera"] = node.getParent().name()

    # Sequence render mel function.
    data["sequence_render_function"] = cmds.renderer(
        cmds.getAttr("defaultRenderGlobals.currentRenderer"),
        query=True,
        renderSequenceProcedure=True
    )

    # Get resolution.
    data["width"] = pc.getAttr("defaultResolution.width")
    data["height"] = pc.getAttr("defaultResolution.height")

    # Render sequence.
    mel.eval(
        "{sequence_render_function}({width}, {height}, \"{camera}\", "
        "\"{save_to_render_view}\")".format(**data)
    )

    # Copy images out of "tmp" folder, because sequence rendering stores in
    # "tmp".
    first_image_path = pc.renderSettings(firstImageName=True, fullPath=True)[0]
    first_image_name = os.path.basename(first_image_path)
    images_directory = os.path.dirname(first_image_path)
    tmp_directory = os.path.join(images_directory, "tmp")
    closest_match = difflib.get_close_matches(
        first_image_name, os.listdir(tmp_directory)
    )[0]

    shutil.move(
        os.path.join(tmp_directory, closest_match),
        os.path.join(images_directory, first_image_name)
    )


def render_sequence(start_frame, end_frame):
    try:
        for count in range(start_frame, end_frame + 1):
            render_frame(count)
    except:
        print(traceback.format_exc())
