import socket

from maya import cmds


def open_deadline_port():

    cmds.commandPort(name=":7005", sourceType="python")
    print("Deadline port is open.")

    # Reply to Deadline server waiting on Maya boot.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ("localhost", 10000)
    sock.connect(server_address)


cmds.evalDeferred(open_deadline_port, lowestPriority=True)
