"""Static checks for the non-root container runtime contract."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_mount_points_are_owned_before_switching_user() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "mkdir -p /data /var/lib/autogematria" in dockerfile
    assert (
        "chown -R autogematria:autogematria /app /data /var/lib/autogematria"
        in dockerfile
    )
    assert dockerfile.index("chown -R autogematria:autogematria") < dockerfile.index(
        "USER autogematria"
    )


def test_generated_corpus_is_not_baked_into_the_image() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "COPY data" not in dockerfile
    assert "data" in dockerignore
