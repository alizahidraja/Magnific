"""Typer CLI for Magnific."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer

from magnific.config import load_workflow_config
from magnific.config_generator import generate_config_file
from magnific.job import JobManager
from magnific.models import StageName
from magnific.orchestrator import Orchestrator
from magnific.utils.logging import setup_logging

app = typer.Typer(
    name="magnific",
    help="Config-driven creative pipeline: story → preview → video.",
    no_args_is_help=True,
)


def _parse_stage(value: str | None) -> StageName | None:
    if value is None:
        return None
    return StageName(value)


@app.command("generate-config")
def generate_config(
    idea: str = typer.Option(..., "--idea", help="Creative idea text"),
    output: Path = typer.Option(
        Path("workflow.yaml"),
        "--output",
        "-o",
        help="Where to write generated workflow config",
    ),
    configs_dir: Optional[Path] = typer.Option(
        None,
        "--configs-dir",
        help="Directory containing default prompts and templates",
    ),
    mock: bool = typer.Option(
        False,
        "--mock/--live",
        help="Mock config skeleton (default: live template merge only)",
    ),
) -> None:
    """Generate workflow.yaml from an idea."""
    setup_logging()
    path = generate_config_file(
        idea,
        output.resolve(),
        configs_dir=configs_dir,
        use_mock=mock,
    )
    typer.echo(f"Wrote config: {path}")


@app.command("run")
def run_pipeline(
    config: Path = typer.Option(..., "--config", help="Workflow YAML/JSON/TOML"),
    from_stage: Optional[str] = typer.Option(
        None,
        "--from-stage",
        help="Start at stage: story, preview, or video",
    ),
    to_stage: Optional[str] = typer.Option(
        None,
        "--to-stage",
        help="Stop after stage (e.g. story only: --from-stage story --to-stage story)",
    ),
    job_id: Optional[str] = typer.Option(
        None,
        "--job-id",
        help="Resume a specific job UUID (writes job_id into config)",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Offline mode: placeholder PNG/MP4, no API calls (for tests/CI only)",
    ),
    fresh: bool = typer.Option(
        False,
        "--fresh",
        help="Start a new job (clears job_id in config before run)",
    ),
) -> None:
    """Execute pipeline for a workflow config."""
    setup_logging()
    cfg_path = config.resolve()
    workflow = load_workflow_config(cfg_path)
    if fresh:
        workflow.job_id = None
    if job_id:
        workflow.job_id = UUID(job_id)
    if not mock and not os.environ.get("GOOGLE_API_KEY", "").strip():
        typer.echo(
            "Error: GOOGLE_API_KEY is not set. Export your key for a live run, or pass --mock.",
            err=True,
        )
        raise typer.Exit(code=1)
    if mock:
        typer.echo("Running in MOCK mode (no Google API calls).", err=True)
    else:
        typer.echo("Running in LIVE mode (Gemini + Veo). This may take several minutes.", err=True)
    result = asyncio.run(
        Orchestrator(
            workflow,
            cfg_path,
            from_stage=_parse_stage(from_stage),
            to_stage=_parse_stage(to_stage),
            use_mock=mock,
        ).run()
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("status")
def status(
    job_id: str = typer.Option(..., "--job-id", help="Job UUID"),
    jobs_dir: Path = typer.Option(Path("jobs"), "--jobs-dir", help="Jobs root directory"),
) -> None:
    """Print job status from on-disk metadata and manifests."""
    setup_logging()
    mgr = JobManager.from_existing_job(jobs_dir.resolve(), UUID(job_id))
    typer.echo(json.dumps(mgr.status_summary(), indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
