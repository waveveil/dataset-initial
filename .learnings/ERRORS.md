# Errors

Command failures and integration errors.

---

## [ERR-20260814-001] explore-agent-model

**Logged**: 2026-08-14T00:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
Three parallel Explore agents failed before inspecting the repository because their selected default model was unavailable.

### Error
```
There's an issue with the selected model (deepseek-v4-pro). It may not exist or you may not have access to it.
```

### Context
- Operation attempted: parallel read-only exploration of frontend, backend, and tests.
- Agent type: Explore.
- All three agents inherited the unavailable `deepseek-v4-pro` model and terminated immediately.
- No repository findings were produced.

### Suggested Fix
Retry Explore agents with an explicit available model override such as `sonnet`, or perform the repository exploration with direct read-only Glob/Grep/Read tools if agent configuration remains unavailable.

### Metadata
- Reproducible: yes
- Related Files: none

---
