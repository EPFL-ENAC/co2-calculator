"""Pod identity for multi-pod deployments."""

import os
import socket

POD_ID: str = os.environ.get("HOSTNAME", socket.gethostname())
