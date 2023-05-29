import os
import shutil
import tempfile

from maya import mel, cmds
import maya.app.renderSetup.model.renderSetup as renderSetup


def render_frame(frame):

    # Set frame range.
    render_globals = "defaultRenderGlobals"
    cmds.setAttr(render_globals + ".startFrame", frame)
    cmds.setAttr(render_globals + ".endFrame", frame)

    # Collect sequence render data.
    data = {
        "sequence_render_function": "",
        "camera": "persp",
        "width": 0,
        "height": 0,
        "save_to_render_view": ""
    }

    # Get render camera.
    for node in cmds.ls(type="camera"):
        if cmds.getAttr(node + ".renderable"):
            data["camera"] = cmds.listRelatives(
                node, parent=True, fullPath=True
            )[0]

    # Sequence render mel function.
    data["sequence_render_function"] = cmds.renderer(
        cmds.getAttr("defaultRenderGlobals.currentRenderer"),
        query=True,
        renderSequenceProcedure=True
    )

    # Get resolution.
    data["width"] = cmds.getAttr("defaultResolution.width")
    data["height"] = cmds.getAttr("defaultResolution.height")

    # Render sequence.
    mel.eval(
        "{sequence_render_function}({width}, {height}, \"{camera}\", "
        "\"{save_to_render_view}\")".format(**data)
    )


def render_sequence(start_frame, end_frame, renderlayer_name=None):
    # Evaluate pre render mel.
    pre_mel = cmds.getAttr("defaultRenderGlobals.preMel")
    if pre_mel:
        print("Evaluating Pre Render MEL:\n{}".format(pre_mel))
        mel.eval(pre_mel)

    # Setting output to local temp directory.
    output_path = os.path.join(
        cmds.workspace(query=True, rootDirectory=True),
        cmds.workspace(fileRuleEntry="images")
    ).replace("\\", "/")

    temp_path = tempfile.mkdtemp().replace("\\", "/")
    cmds.workspace(fileRule=["images", temp_path])

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
        first_image = cmds.renderSettings(
            firstImageName=True,
            fullPath=True
        )[0]
        expected_output_path = os.path.join(
            cmds.workspace(query=True, rootDirectory=True),
            cmds.workspace(fileRuleEntry="images")
        )
        prefix_directories = os.path.dirname(first_image).replace(
            expected_output_path, ""
        )

        renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
        actual_prefix_directories = os.path.dirname(first_image).replace(
            expected_output_path, ""
        )
        # Maya Hardware seems to always have "masterLayer" as the layer name.
        if renderer == "mayaHardware2":
            actual_prefix_directories = actual_prefix_directories.replace(
                layer.name(), "masterLayer"
            )

        actual_output_path = (
            os.path.join(expected_output_path, "tmp") +
            actual_prefix_directories
        )
        # Vray seems to avoid the "tmp" subdirectory.
        if renderer == "vray":
            actual_output_path = (
                expected_output_path + actual_prefix_directories
            )

        for f in os.listdir(actual_output_path):
            source = os.path.join(actual_output_path, f).replace("\\", "/")

            # Rendering through Arnold adds "_1" to the file name.
            destination_filename = f.replace("_1", "")
            # Rendering through Maya Hardware seems to always be "masterLayer"
            # as the layer name.
            destination_filename = destination_filename.replace(
                "masterLayer", layer.name()
            )

            destination = os.path.join(
                expected_output_path + prefix_directories, destination_filename
            ).replace("\\", "/")

            destination = destination.replace(temp_path, output_path)

            if not os.path.exists(os.path.dirname(destination)):
                os.makedirs(os.path.dirname(destination))

            print("Moving \"{}\" to \"{}\"".format(source, destination))

            shutil.move(source, destination)

            # Validate destination file.
            msg = "{} was not moved correctly from {}".format(
                destination, source
            )
            assert os.path.exists(destination), msg

            if os.path.exists(destination):
                print("{} moved to {}".format(source, destination))

    # Clean up.
    print("Cleaning up: {}".format(temp_path))
    shutil.rmtree(temp_path)

    cmds.workspace(fileRule=["images", output_path])
