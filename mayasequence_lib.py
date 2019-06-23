import os
import shutil
import difflib

import pymel.core as pc

from maya import mel, cmds
import maya.app.renderSetup.model.renderSetup as renderSetup


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


def render_sequence(start_frame, end_frame):
    # Get all renderable layers.
    render_setup = renderSetup.instance()
    render_layers = render_setup.getRenderLayers()

    renderable_layers = []
    for layer in render_layers:
        if layer.isRenderable():
            renderable_layers.append(layer)

    print(
        "Renderable layers: {}".format([x.name() for x in renderable_layers])
    )

    for layer in renderable_layers:
        print("Switching to: {}".format(layer.name()))
        render_setup.switchToLayer(layer)
        for count in range(start_frame, end_frame + 1):
            print("Rendering frame: {}".format(count))
            render_frame(count)
