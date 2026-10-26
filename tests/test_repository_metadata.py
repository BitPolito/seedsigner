"""Keep downstream release declarations aligned without production dependencies."""

import ast
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def release_metadata():
    output = subprocess.check_output(
        ["sh", "-c", '. ./scripts/release.env; printf "%s\\n" '
         '"$BITPOLITO_VERSION" "$SEEDSIGNER_APP_BASE_COMMIT" '
         '"$SEEDSIGNER_OS_COMMIT" "$BITPOLITO_APP_REPOSITORY"'],
        cwd=ROOT, text=True,
    )
    return output.splitlines()


def test_release_declarations_match():
    version, app, os_commit, repository = release_metadata()
    theme = json.loads((ROOT / "design/bitpolito-theme.json").read_text())
    assert theme["release"] == version
    assert theme["upstream"]["application_commit"] == app
    assert theme["upstream"]["os_commit"] == os_commit
    controller = ast.parse((ROOT / "src/seedsigner/controller.py").read_text())
    versions = [
        node.value.value for node in ast.walk(controller)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        and any(isinstance(target, ast.Name) and target.id == "VERSION"
                for target in node.targets)
    ]
    assert versions == [version]
    package = (ROOT / "pyproject.toml").read_text()
    assert re.search(r'^version = "([^"]+)"$', package, re.M)[1] == version.replace(
        "-bitpolito.", "+bitpolito."
    )
    workflow = (ROOT / ".github/workflows/build.yml").read_text()
    for name, value in (("BITPOLITO_VERSION", version),
                        ("SEEDSIGNER_OS_COMMIT", os_commit),
                        ("BITPOLITO_APP_REPOSITORY", repository)):
        assert re.search(rf'^  {name}: "([^"]+)"$', workflow, re.M)[1] == value


def test_current_review_is_complete_and_has_no_legacy_sets():
    version = release_metadata()[0]
    review = ROOT / "design/review"
    assert sorted(path.name for path in review.iterdir() if path.is_dir()) == [version]
    folder = review / version / "en/full"
    manifest = json.loads((folder / "manifest.json").read_text())
    for category in manifest["categories"].values():
        assert (folder / category["sheet"]).is_file()
        assert category["count"] == len(category["screens"])
        assert len(category["screens"]) == len(set(category["screens"]))


def test_development_outputs_are_ignored():
    paths = ["artifacts/release/candidate.img", ".build/pi0/cache",
             ".venv-simulator/bin/python", ".simulator-runtime/lib/local.so",
             "tests/__pycache__/local.pyc", ".pytest_cache/README.md"]
    result = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT,
                            input="\n".join(paths) + "\n", text=True,
                            capture_output=True, check=True)
    assert result.stdout.splitlines() == paths
