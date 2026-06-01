# Empty __init__.py to make tasks a Python package.
#
# Plan 310-C: handler modules MUST be imported (so their @register
# decorators populate the registry) before the runner dispatches.  We
# do NOT do those imports here, because ``app/services/audit_service.py``
# imports ``app.tasks.audit_sync_tasks`` early in app startup, and
# any side-effect imports here would create a circular import via
# the ingestion provider factory.
#
# The runtime guarantee is provided by ``app.tasks.bootstrap`` —
# imported by both ``app.main`` (so the lifespan context has the
# registry primed before serving requests) and by ``app.tasks.runner``
# (defence-in-depth so an out-of-band caller still works).
