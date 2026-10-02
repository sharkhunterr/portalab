"""Connectors permissions (T003).

The keys already have owners: ``services.read`` / ``services.manage`` belong to the core catalog (spec 003,
CD-033), ``connectors.manage`` (sensitive) to Administration (020) and ``services.purge`` to Privacy (021).
This module only names them, so routes and tests share one spelling.
"""

SERVICES_READ = "services.read"
SERVICES_MANAGE = "services.manage"
CONNECTORS_MANAGE = "connectors.manage"
INFRASTRUCTURE_READ = "infrastructure.read"  # core catalog: configuration details of services
SERVICES_PURGE = "services.purge"
