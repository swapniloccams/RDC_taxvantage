"""Pipeline package initialization."""

from .coordinator import run_pipeline, PipelineError

__all__ = [
    "run_pipeline",
    "PipelineError",
]
