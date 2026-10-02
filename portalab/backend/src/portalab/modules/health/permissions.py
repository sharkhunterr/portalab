"""Health permissions (T003). All keys are declared by the core catalog (spec 003, CD-033):
``services.read`` (state, availability), ``infrastructure.read`` (metrics, uptime details, errors) and
``services.manage`` (maintenance, operations — sensitive)."""

SERVICES_READ = "services.read"
INFRASTRUCTURE_READ = "infrastructure.read"
SERVICES_MANAGE = "services.manage"
