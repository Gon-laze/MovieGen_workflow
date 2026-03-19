from __future__ import annotations

from pathlib import Path

import yaml

from .models import ProjectSpec


def load_project_spec(path: Path) -> ProjectSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ProjectSpec.model_validate(data)
