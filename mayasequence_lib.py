import os
import shutil
import tempfile

import pymel.core as pm

from maya import mel, cmds
import maya.app.renderSetup.model.renderSetup as renderSetup


def render_frame(frame):

    # Set frame range.
    render_globals = pm.PyNode("defaultRenderGlobals")
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
    for node in pm.ls(type="camera"):
        if node.renderable.get():
            data["camera"] = node.getParent().name()

    # Sequence render mel function.
    data["sequence_render_function"] = cmds.renderer(
        cmds.getAttr("defaultRenderGlobals.currentRenderer"),
        query=True,
        renderSequenceProcedure=True
    )

    # Get resolution.
    data["width"] = pm.getAttr("defaultResolution.width")
    data["height"] = pm.getAttr("defaultResolution.height")

    # Render sequence.
    mel.eval(
        "{sequence_render_function}({width}, {height}, \"{camera}\", "
        "\"{save_to_render_view}\")".format(**data)
    )


def render_sequence(start_frame, end_frame, renderlayer_name=None):
    # Setting output to local temp directory.
    output_path = os.path.join(
        cmds.workspace(query=True, rootDirectory=True),
        pm.workspace.fileRules["images"]
    ).replace("\\", "/")

    temp_path = tempfile.mkdtemp().replace("\\", "/")
    pm.workspace.fileRules["images"] = temp_path

    # Get all renderable layers.
    render_setup = renderSetup.instance()
    render_layers = render_setup.getRenderLayers()

    renderable_layers = []
    for layer in render_layers:
        # Add all render layers when none is specified.
        if renderlayer_name is None and layer.isRenderable():
            renderable_layers.append(layer)

        # Only add the render layer if its requested.
        if ("rs_" + layer.name()) == renderlayer_name:
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

        # Move renders to expected output path.
        first_image = pm.renderSettings(
            firstImageName=True,
            fullPath=True
        )[0]
        expected_output_path = os.path.join(
            cmds.workspace(query=True, rootDirectory=True),
            pm.workspace.fileRules["images"]
        )
        prefix_directories = os.path.dirname(first_image).replace(
            expected_output_path, ""
        )
        actual_output_path = (
            os.path.join(expected_output_path, "tmp") + prefix_directories
        )
        for f in os.listdir(actual_output_path):
            source = os.path.join(actual_output_path, f).replace("\\", "/")
            destination = os.path.join(
                expected_output_path + prefix_directories, f.replace("_1", "")
            ).replace("\\", "/")

            destination = destination.replace(temp_path, output_path)

            if not os.path.exists(os.path.dirname(destination)):
                os.makedirs(os.path.dirname(destination))

            print("Moving \"{}\" to \"{}\"".format(source, destination))

            shutil.move(source, destination)

    # Clean up.
    print("Cleaning up: {}".format(temp_path))
    shutil.rmtree(temp_path)

    pm.workspace.fileRules["images"] = output_path
