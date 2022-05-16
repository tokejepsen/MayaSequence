import socket
import tempfile
import os
import random

from Deadline.Plugins import (
    DeadlinePlugin,
    PluginType
)
from FranticX.Processes import ManagedProcess
from System.Diagnostics import ProcessPriorityClass


######################################################################
# This is the function that Deadline calls to get an instance of the
# main DeadlinePlugin class.
######################################################################
def GetDeadlinePlugin():
    return MayaSequence()


######################################################################
# This is the function that Deadline calls when the plugin is no
# longer in use so that it can get cleaned up.
######################################################################
def CleanupDeadlinePlugin(deadlinePlugin):
    deadlinePlugin.Cleanup()


######################################################################
# This is the main DeadlinePlugin class for MayaSequence.
######################################################################
class MayaSequence(DeadlinePlugin):

    # Variable to hold the Managed Process object.
    Process = None

    # Variable to hold boot state of Maya
    maya_booted = False

    # Variable to hold scene loaded state
    scene_loaded = False

    # Variable to hold connetion to Maya.
    connection = None

    # Variable to hold previous logging.
    previous_log = ""

    # Hook up the callbacks in the constructor.
    def __init__(self):
        self.InitializeProcessCallback += self.InitializeProcess
        self.StartJobCallback += self.StartJob
        self.RenderTasksCallback += self.RenderTasks
        self.EndJobCallback += self.EndJob

    # Clean up the plugin.
    def Cleanup(self):
        del self.InitializeProcessCallback
        del self.StartJobCallback
        del self.RenderTasksCallback
        del self.EndJobCallback

        # Clean up the managed process object.
        if self.Process:
            self.Process.Cleanup()
            del self.Process

    # Called by Deadline to initialize the process.
    def InitializeProcess(self):
        self.launch_port = random.randrange(10000, 11000)
        self.render_port = random.randrange(7005, 8000)

        self.SetEnvironmentAndLogInfo(
            "MAYASEQUENCE_LAUNCH_PORT", str(self.launch_port)
        )
        self.SetEnvironmentAndLogInfo(
            "MAYASEQUENCE_RENDER_PORT", str(self.render_port)
        )

        # Set the plugin specific settings.
        self.SingleFramesOnly = False
        self.PluginType = PluginType.Advanced

        self.SetEnvironmentAndLogInfo("MAYA_DEBUG_ENABLE_CRASH_REPORTING", "0")
        self.SetEnvironmentAndLogInfo(
            "MAYA_DISABLE_CIP",
            "1",
            description="ADSK Customer Involvement Program"
        )
        self.SetEnvironmentAndLogInfo(
            "MAYA_DISABLE_CER",
            "1",
            description="ADSK Customer Error Reporting"
        )
        self.SetEnvironmentAndLogInfo(
            "MAYA_DISABLE_CLIC_IPM",
            "1",
            description="ADSK In Product Messaging"
        )

        self.SetEnvironmentAndLogInfo("PYTHONPATH", self.GetPluginDirectory())

        # Maya logging.
        self.maya_logging_directory = tempfile.mkdtemp()
        self.maya_logging_file = os.path.join(
            self.maya_logging_directory, "maya_script_editor_output.txt"
        )
        self.SetEnvironmentAndLogInfo(
            "MAYA_CMD_FILE_OUTPUT", self.maya_logging_file
        )

    def SetEnvironmentAndLogInfo(self, envVar, value, description=None):
        """
        Sets an environment variable and prints a message to the log
        :param envVar: The environment variable that is going to be set
        :param value: The value that is the environment variable is being set
            to
        :param description: An optional description of the environment variable
            that will be added to the log.
        :return: Nothing
        """
        self.LogInfo(
            "Setting {0}{1} environment variable to {2} for this"
            " session".format(
                envVar,
                " ({0})".format(description) if description else "",
                value
            )
        )
        self.SetProcessEnvironmentVariable(envVar, value)

    # Called by Deadline when the job starts.
    def StartJob(self):
        self.ProcessName = "MayaSequence"
        self.Process = MayaSequenceProcess(self)

        self.StartMonitoredManagedProcess(
            self.ProcessName, self.Process
        )

    def wait_for_maya_boot(self):
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Bind the socket to the port
        server_address = ("localhost", self.launch_port)
        self.LogInfo("Starting up on {}".format(server_address))
        sock.bind(server_address)

        sock.settimeout(120)

        # Listen for incoming connections
        sock.listen(1)

        while True:
            # Wait for a connection
            self.LogInfo("Waiting for a connection to Maya.")
            connection, client_address = sock.accept()
            break

    def send_to_maya(self, cmd):
        self.LogInfo("Sending: {}".format(repr(cmd)))
        self.connection.send(cmd)
        data = self.connection.recv(4096)
        self.LogInfo(data)
        self.read_maya_script_editor_output()
        return data

    def read_maya_script_editor_output(self):
        with open(self.maya_logging_file) as f:
            log = f.read().replace(self.previous_log, "")
            self.LogInfo(log)
            self.previous_log += log

    # Called by Deadline for each task the Slave renders.
    def RenderTasks(self):

        # Booting Maya.
        if not self.maya_booted:
            self.LogInfo("Waiting until maya is ready to go.")
            self.wait_for_maya_boot()
            self.maya_booted = True
            self.read_maya_script_editor_output()

            # Establish connection.
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect(("localhost", self.render_port))

        # Turn off cached playback. This can cause issues when renders are
        # jumping back and forth on the timeline.
        self.send_to_maya(
            "from maya.plugin.evaluator.cache_preferences"
            " import CachePreferenceEnabled;"
            "CachePreferenceEnabled().set_value(False)"
        )

        # Load scene.
        scene_file = self.GetPluginInfoEntryWithDefault("SceneFile", "")
        if not self.scene_loaded:
            self.LogInfo("Loading scene: \"{}\".".format(scene_file))
            self.send_to_maya(
                "import pymel.core as pc;"
                "pc.openFile(\"{}\", force=True)".format(
                    scene_file.strip().replace("\\", "/")
                )
            )
            self.scene_loaded = True

        # Rendering frames.
        self.LogInfo("Rendering frames: {} to {}.".format(
                self.GetStartFrame(),
                self.GetEndFrame()
            )
        )

        renderlayer = self.GetPluginInfoEntryWithDefault("RenderLayer", "")
        results = None
        if renderlayer:
            results = self.send_to_maya(
                "import mayasequence_lib;"
                "mayasequence_lib.render_sequence({}, {}, \"{}\")".format(
                    self.GetStartFrame(),
                    self.GetEndFrame(),
                    renderlayer
                )
            )
        else:
            results = self.send_to_maya(
                "import mayasequence_lib;"
                "mayasequence_lib.render_sequence({}, {})".format(
                    self.GetStartFrame(),
                    self.GetEndFrame()
                )
            )

        if "No module named mayasequence_lib" in results:
            raise ImportError(
                "No module named mayasequence_lib in Maya session."
            )

    # Called by Deadline when the job ends.
    def EndJob(self):
        self.ShutdownMonitoredManagedProcess(self.ProcessName)


######################################################################
# This is the ManagedProcess class that is launched above.
######################################################################
class MayaSequenceProcess(ManagedProcess):
    deadlinePlugin = None

    # Hook up the callbacks in the constructor.
    def __init__(self, deadlinePlugin):
        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument
        self.deadlinePlugin = deadlinePlugin

    # Clean up the managed process.
    def Cleanup(self):
        # Clean up stdout handler callbacks.
        for stdoutHandler in self.StdoutHandlers:
            del stdoutHandler.HandleCallback

        del self.InitializeProcessCallback
        del self.RenderExecutableCallback
        del self.RenderArgumentCallback

    # Called by Deadline to initialize the process.
    def InitializeProcess(self):
        # Set the ManagedProcess specific settings.
        self.ProcessPriority = ProcessPriorityClass.BelowNormal
        self.UseProcessTree = True
        self.StdoutHandling = True
        self.PopupHandling = True

        # Set the stdout handlers.
        self.AddStdoutHandlerCallback(
            "WARNING:.*").HandleCallback += self.HandleStdoutWarning
        self.AddStdoutHandlerCallback(
            "ERROR:(.*)").HandleCallback += self.HandleStdoutError

    # Callback for when a line of stdout contains a WARNING message.
    def HandleStdoutWarning(self):
        self.deadlinePlugin.LogWarning(self.GetRegexMatch(0))

    # Callback for when a line of stdout contains an ERROR message.
    def HandleStdoutError(self):
        self.deadlinePlugin.FailRender(
            "Detected an error: " + self.GetRegexMatch(1)
        )

    # Callback to get the executable used for rendering.
    def RenderExecutable(self):
        version = self.deadlinePlugin.GetPluginInfoEntry("Version")
        return self.deadlinePlugin.GetConfigEntry("RenderExecutable" + version)

    # Callback to get the arguments that will be passed to the executable.
    def RenderArgument(self):
        path = self.deadlinePlugin.GetPluginInfoEntryWithDefault(
            "ProjectPath", ""
        )
        arguments = " -proj \"{}\"".format(
            path.strip().replace("\\", "/")
        )
        return arguments
