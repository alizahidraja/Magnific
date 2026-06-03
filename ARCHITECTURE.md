# Magnific Architecture

Magnific is a config-driven pipeline that takes a creative idea and two reference images, then turns them into a set of short scene-based videos. The whole thing is split into stages so each step can be run on its own, resumed later, or debugged without rerunning everything.

Each job lives in its own folder on disk. Stages do not share memory or hidden state — they only talk through manifests and config files.

---

## How the pipeline works

```
idea + ref_a.png + ref_b.png + workflow.yaml
       |
       v
generate-config
       |
       v
story stage -> story_manifest.json
       |
       v
preview stage -> preview images + preview_manifest.json
       |
       v
video stage -> mp4s + video_manifest.json
```
The basic flow is:

1. take the idea and reference images  
2. turn them into structured scenes  
3. generate preview stills for each scene  
4. generate short videos from those previews  

At the end, everything sits inside a single job folder, which makes it easy to inspect or resume.

---

## Inputs

- A text idea  
- Two reference images  
- A workflow config file  

The config file controls things like:
- model names  
- prompt files  
- output paths  
- retry settings  
- concurrency limits  
- video settings  

---

## Outputs

Each run gets its own job folder.
```
jobs/<job_id>/
  job.json
  manifests/
    story_manifest.json
    preview_manifest.json
    video_manifest.json
  previews/
  videos/
  logs/
```
The manifests are the important part. They are the record of what happened in each stage, what succeeded, what failed, and what can be resumed.

---

## Core pieces

### CLI

The CLI is the entry point for the whole repo.

- generate-config — create a workflow config from an idea  
- run — run the pipeline  
- status — check job progress  

---

### Config loader

All tunable values should come from config, not hardcoded Python.

Includes:
- model names  
- prompt paths  
- concurrency limits  
- retry behavior  
- output folders  
- video settings  

---

### Job manager

Every run gets a unique job ID.

Handles:
- creating job directory  
- writing job metadata  
- isolating outputs  

---

### Manifest manager

Each stage writes a manifest.

Each scene tracks:
- scene_id  
- status  
- outputs  
- errors  

This is what enables resume.

---

### Stages

#### Story stage
- Input: idea + images  
- Output: story_manifest.json  

#### Preview stage
- Input: story manifest  
- Output: images + preview_manifest.json  
- Runs concurrently with limits  

#### Video stage
- Input: preview outputs  
- Output: mp4s + video_manifest.json  
- Uses async polling  

---

## Concurrency

Preview:
- async per scene  
- bounded with semaphore  

Video:
- submit jobs in parallel  
- poll in parallel  

---

## Failure handling

- retry transient + rate limits  
- no retry for safety issues  
- do not crash whole pipeline  
- log errors per scene  

---

## Resume behavior

- skip completed scenes  
- resume from any stage  
- rely on manifests, not guessing  

---

## Extensibility

Easy to:
- add new stages  
- swap providers  
- extend pipeline  

---

## Design choices

- file-based state (no DB)  
- manifest-driven pipeline  
- isolated job folders  

---

## Module map
```
src/magnific/
  cli.py
  config.py
  models.py
  job.py
  manifests.py
  retry.py
  google_clients.py
  orchestrator.py
  stages/
  utils/
```
---

## Summary

Magnific is built around:
- config-driven execution  
- manifest-based state  
- resumable stages  
- async concurrency  

Simple, but structured enough to extend.