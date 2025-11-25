"""Template rendering utilities built on Jinja2."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

TEMPLATES_ENV_VAR = "SELF_DEPLOY_TEMPLATES_DIR"


def _templates_base_dir() -> Path:
    """Resolve the root templates directory, overridable via env var."""
    override = os.environ.get(TEMPLATES_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return (Path(__file__).resolve().parent.parent / "templates").resolve()


def _environment(base_dir: Path) -> Environment:
    """Build a Jinja2 environment configured for file-system templates."""
    return Environment(
        loader=FileSystemLoader(str(base_dir)),
        autoescape=False,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_template(template_path: str, context: Dict[str, Any]) -> str:
    """Render a template under the project's templates/ directory."""
    base_dir = _templates_base_dir()
    env = _environment(base_dir)
    try:
        template = env.get_template(template_path)
    except TemplateNotFound as exc:
        raise FileNotFoundError(f"Template '{template_path}' not found under {base_dir}") from exc
    return template.render(**context)
