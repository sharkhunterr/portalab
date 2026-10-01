# Event Model

Events describe things that happened and decouple producers from consumers.

Conceptual fields:
- event_id
- event_type
- occurred_at
- received_at
- source
- actor/context
- object/reference
- metadata
- version

Examples:
user.created
user.deleted
user.level_up
media.added
media.playback_started
media.playback_finished
service.connected
service.disconnected
service.status_changed
sync.started
sync.completed
sync.failed
ticket.created
ticket.updated
ticket.resolved
incident.created
incident.updated
incident.resolved
maintenance.scheduled
maintenance.started
maintenance.ended
achievement.unlocked
quest.completed
reward.granted
marketplace.purchase
marketplace.unlock
marketplace.refund
project.created
project.vote_added
project.funding_added
project.status_changed
event.started
event.ended
plugin.enabled
plugin.disabled

Consumers must be idempotent where duplicate delivery is possible.

occurred_at = real occurrence time.
received_at = portal receipt time.

History does not imply public visibility.
