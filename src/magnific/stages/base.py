"""Base stage abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from magnific.google_clients import BaseGeminiClient, BaseVeoClient
from magnific.job import JobManager
from magnific.models import StageName, StageResult, WorkflowConfig


@dataclass
class StageContext:
    config: WorkflowConfig
    config_dir: Path
    job: JobManager
    gemini: BaseGeminiClient
    veo: BaseVeoClient


class BaseStage(ABC):
    name: StageName

    @abstractmethod
    async def run(self, ctx: StageContext) -> StageResult:
        """Execute stage and return result with manifest path."""
