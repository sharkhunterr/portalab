# Extending Media

All registries are owner-tagged: everything a plugin registered disappears with `unregister(owner)`.

## A new media type

```python
from portalab.capabilities.media_core import register_media_type

register_media_type("radio.show", "radio:kind.show", owner="plugin:radio", finished_threshold=0.5)
```

Plugin kinds are namespaced `<plugin>.<kind>`; `finished_threshold=None` means only an explicit ending counts.

## A detail-page block

```python
from portalab.capabilities.media_core import DetailBlock, register_detail_block

async def listeners(object_id, viewer):
    return {"rows": [["Listeners", "1 204"]]}

register_detail_block(
    DetailBlock("radio.listeners", "plugin:radio", "radio:block.listeners", "facts", listeners,
                required_permission="plugin:radio.use", kinds=("radio.show",))
)
```

Templates are declarative (`facts`, `list`, `text`, `links`); each block loads with a timeout, is hidden
without its permission and a failing block only shows its own unavailable state.

## Statistics, widgets, palette, notifications

Statistic packs are JSON definitions over media events (`backend/definitions/packs/{media,playback,reading,
gaming}.json`); aggregatable payload fields are `kind`, `percent` (playback) and `state` (requests).
Widgets, search providers/actions and notification categories use the 009, 008 and 010 SDKs.

## Campaign and automation conditions

`activity.attributes` returns `media_kind`, canonical (lower-case) `genres`, `title` and
`original_title` for any `media.*` event carrying an `object`.
