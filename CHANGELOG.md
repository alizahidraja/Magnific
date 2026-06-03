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