# Changelog

All notable design decisions and updates for Magnific.

## 0.1.0 — Foundation

### Added

- Base `src/magnific` package with Typer CLI:
  - generate-config
  - run
  - status
- Pydantic models for config, manifests, and job metadata
- Pipeline stages:
  - story
  - preview
  - video
- Manifest system with per-scene tracking
- Retry logic with exponential backoff
- `google_clients` layer for API abstraction
- Async concurrency for preview + video stages
- Example configs under `configs/`
- Pytest suite with mocked APIs

---

### Trade-offs

| Decision                     | Why                          | Revisit                    |
| ---------------------------- | ---------------------------- | -------------------------- |
| JSON manifests instead of DB | Simple, easy to inspect      | Add SQLite later if needed |
| Async execution              | Good for API-heavy workloads | Maybe add sync debug mode  |
| Pydantic models              | Better validation than dicts | Keep                       |
| API wrapper layer            | Easier to mock and test      | Could expand later         |
| External prompt files        | Easier iteration             | Add validation             |
| No Docker                    | Not needed here              | Add later if needed        |

---

### Notes

The main goal here was not just to make it work, but to structure it properly:

- stages are independent  
- failures are isolated  
- everything is inspectable  
- resume is straightforward  

---

## Next improvements

- better integration tests with real APIs  
- prompt validation  
- structured logging per job  
- config validation before running  


## 0.2.0

### Added
- Clear separation between mock and live execution (`--mock` required for mocks)
- Explicit validation for `GOOGLE_API_KEY` in live runs
- Stage-level logging with duration metrics
- Placeholder detection for preview/video outputs to support correct resume behavior
- `--fresh` flag to force new job execution

### Fixed
- Video duration handling aligned with Veo constraints
- Config validation rejects unsupported durations (e.g. 5s)
- Improved reliability when resuming from video stage

### Notes
- Video generation still requires further stabilization with live Veo APIs

## 0.3.0

### Fixed
- Fixed video download in `HttpVeoClient` (was not saving output correctly, causing video stage to complete without files) 

### Notes
- Noticed video stage was taking time but producing no output, traced it back to a bug in the download step rather than generation itself