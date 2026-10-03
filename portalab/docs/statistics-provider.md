# Using statistics from another module (spec 017)

Never read `stats.*` tables: ask the provider, as the acting principal.

```python
from portalab.capabilities.statistics import PROVIDER, Period, SubjectRef

provider = capabilities.system_providers(PROVIDER)[0].provider
result = await provider.get(
    "users.active_by_day",
    viewer=principal,                       # a user, or an AI/automation principal acting for one
    period=Period("last_n_days", days=30),
    subject=SubjectRef("user", user_id),    # personal statistics only; defaults to the viewer
)
if result.state in ("available", "partial", "stale"):
    use(result.value, result.series, result.trend)
```

`result.state` is one of `available | partial | stale | locked | unavailable | insufficient_data |
no_data`; `StatisticForbidden` (403) and `UnknownStatistic` (404) are raised for statistics the viewer may
not see or that do not exist. Values are identical for every consumer given the same inputs.
