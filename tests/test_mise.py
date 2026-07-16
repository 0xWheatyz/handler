"""The mise-config gate: which filenames count, and the [tasks.test] check."""

from __future__ import annotations

from handler.control import mise


def test_no_config_is_no_config(tmp_path):
    assert mise.has_config(str(tmp_path)) is False
    assert mise.has_test_task(str(tmp_path)) is False


def test_dotless_mise_toml_is_accepted(tmp_path):
    (tmp_path / "mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    assert mise.has_config(str(tmp_path)) is True
    assert mise.has_test_task(str(tmp_path)) is True


def test_dotted_mise_toml_is_accepted(tmp_path):
    (tmp_path / ".mise.toml").write_text("[tasks.test]\nrun = 'go test ./...'\n")
    assert mise.has_test_task(str(tmp_path)) is True


def test_config_under_dot_config_dir(tmp_path):
    cfg = tmp_path / ".config" / "mise"
    cfg.mkdir(parents=True)
    (cfg / "config.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    assert mise.has_test_task(str(tmp_path)) is True


def test_config_without_test_task_fails_the_gate(tmp_path):
    (tmp_path / "mise.toml").write_text("[tasks.lint]\nrun = 'ruff check .'\n")
    assert mise.has_config(str(tmp_path)) is True
    assert mise.has_test_task(str(tmp_path)) is False


def test_corrupt_config_is_not_a_test_task(tmp_path):
    (tmp_path / "mise.toml").write_text("this = = not valid toml")
    assert mise.has_config(str(tmp_path)) is True
    assert mise.has_test_task(str(tmp_path)) is False
