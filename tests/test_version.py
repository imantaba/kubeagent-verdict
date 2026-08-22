import tomllib
from pathlib import Path

import kubeagent_verdict

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_pyproject_version_matches_package_version():
    doc = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert doc["project"]["version"] == kubeagent_verdict.__version__
