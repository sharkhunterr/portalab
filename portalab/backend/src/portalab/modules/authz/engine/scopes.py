"""Structural scope matching (T019; FR-004, FR-013..015).

A grant applies only inside its scope:

* ``global`` — anywhere;
* ``self`` — the caller's own objects (``resource.owner_id`` is the caller, or no resource: the action targets
  the caller itself, e.g. ``/me``); never another user nor global configuration;
* ``owned`` — an object whose ``owner_id`` is the caller (the resource must carry ``owner_id``);
* ``module`` / ``service`` / ``plugin`` — the resource belongs to that module, service instance or plugin
  (``attributes["module" | "service_id" | "plugin_id"]``; a ``service`` resource's own id also counts).
"""

from uuid import UUID

from portalab.core.authz_port import ResourceRef


def scope_matches(scope_kind: str, scope_ref: str, subject: UUID, resource: ResourceRef | None) -> bool:
    if scope_kind == "global":
        return True
    if scope_kind == "self":
        return resource is None or resource.owner_id == subject
    if resource is None:
        return False
    if scope_kind == "owned":
        return resource.owner_id is not None and resource.owner_id == subject
    attributes = resource.attributes
    if scope_kind == "module":
        return bool(scope_ref) and attributes.get("module") == scope_ref
    if scope_kind == "service":
        if not scope_ref:
            return False
        return attributes.get("service_id") == scope_ref or (
            resource.kind == "service" and resource.id == scope_ref
        )
    if scope_kind == "plugin":
        return bool(scope_ref) and attributes.get("plugin_id") == scope_ref
    return False
