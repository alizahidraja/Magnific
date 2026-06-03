# Magnific

Magnific is a small creative pipeline that takes:

* two reference images
* a text idea

and turns them into:

* structured scenes
* preview stills
* short MP4 clips

The project is structured like a real system: config-driven, resumable, and easy to inspect.

---

## Setup

```bash
git clone <your-repo-url>
cd magnific

python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
export GOOGLE_API_KEY="your-key"
```

---

## Generate a workflow config

```bash
python -m magnific generate-config \
  --idea "Exploring a new country and surfing" \
  -o workflow.yaml
```

This creates a config file that controls models, prompts, concurrency, and output paths.

---

## Run the pipeline

```bash
python -m magnific run --config workflow.yaml
```

This will:

* create a job folder
* generate scenes
* generate preview images
* generate video clips

---

## Run specific stages

```bash
# Only story generation
python -m magnific run --config workflow.yaml --from-stage story --to-stage story

# Resume from preview
python -m magnific run --config workflow.yaml --from-stage preview
```

---

## Check job status

```bash
python -m magnific status --job-id <UUID>
```

---

## Output structure

```text
jobs/<job_id>/
  job.json
  manifests/
    story_manifest.json
    preview_manifest.json
    video_manifest.json
  previews/
  videos/
```

Each stage writes a manifest, which makes the pipeline easy to debug and resume.

---

## Testing

```bash
pytest
```

Tests use mocked API clients, so no real API calls are required.

---

## Notes

The main idea behind the project:

* keep state on disk (not in memory or a DB)
* keep stages independent
* allow partial failures
* make resume simple

Everything else builds on top of that.
