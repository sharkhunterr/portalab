"""Module wiring at the composition root: build each module's context from the kernel services.

Identity (spec 002) is wired with the kernel adapters available today — outbox ``EventPublisher``, interim
``LogAuditSink`` and the filesystem ``BlobStore`` — and with the application's Authorizer. Spec 003 replaces
the audit sink and registers ``authz.admin_authority``; spec 007 replaces the event publisher.
"""

from pathlib import Path

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import LogAuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.event_port import OutboxEventPublisher
from portalab.core.jobs.registry import JobRegistry
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.module import IdentityModule


def default_identity_context(
    database: Database, *, data_dir: Path, capabilities: CapabilityRegistry, authorizer: Authorizer
) -> IdentityContext:
    return IdentityContext(
        database=database,
        events=OutboxEventPublisher(),
        audit=LogAuditSink(),
        capabilities=capabilities,
        blobs=FileSystemBlobStore(data_dir / "blobs"),
        authorizer=authorizer,
    )


def wire_identity(context: IdentityContext, *, jobs: JobRegistry | None = None) -> IdentityModule:
    module = IdentityModule(context)
    module.register_capabilities()
    if jobs is not None:
        module.register_jobs(jobs)
    return module
