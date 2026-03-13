"""Pipeline package initialization."""

from .coordinator import run_pipeline, run_pipeline_from_dict, PipelineError

__all__ = [
    "run_pipeline",
    "run_pipeline_from_dict",
    "PipelineError",
]
