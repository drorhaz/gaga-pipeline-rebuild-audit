"""Thin re-export so pipeline.py can use from .config import CONFIG."""
from .pipeline_config import CONFIG

__all__ = ["CONFIG"]
