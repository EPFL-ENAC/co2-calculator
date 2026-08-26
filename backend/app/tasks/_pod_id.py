"""Pod identity for multi-pod deployments."""

import os
import socket

POD_ID: str = os.environ.get("HOSTNAME", socket.gethostname())

# Routable pod IP (Kubernetes Downward API ``status.podIP``, see
# ``co2-calculator.backendSecretEnv`` in the Helm chart). ``None`` outside
# Kubernetes (local dev, tests) — callers must treat that as "not a
# broadcast target", not fall back to a guess.
POD_IP: str | None = os.environ.get("POD_IP")
