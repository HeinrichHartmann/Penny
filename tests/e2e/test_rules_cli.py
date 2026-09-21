from pathlib import Path

from click.testing import CliRunner

from penny.cli import main
from penny.vault import (
    VaultConfig,
    ensure_vault_initialized,
    latest_rules_path,
    save_rules_snapshot,
)

SAMPLE_RULES = """\
from penny.classify import rule

DEFAULT_CATEGORY = "uncategorized"

@rule("food/bakery")
def bakery(tx):
    return False
"""


def _seed_rules() -> Path:
    """Save a sample rules snapshot and return the vault rules path."""
    config = VaultConfig()
    ensure_vault_initialized(config)
    save_rules_snapshot(SAMPLE_RULES, config)
    return latest_rules_path(config)


def test_rules_show_prints_active_rules():
    _seed_rules()
    runner = CliRunner()
    result = runner.invoke(main, ["rules", "show"])

    assert result.exit_code == 0
    assert "food/bakery" in result.output
    assert "DEFAULT_CATEGORY" in result.output


def test_rules_show_errors_when_no_rules():
    config = VaultConfig()
    ensure_vault_initialized(config)
    # No rules saved — rules dir exists but is empty
    runner = CliRunner()
    result = runner.invoke(main, ["rules", "show"])

    assert result.exit_code != 0
    assert "No rules file found" in result.output


def test_rules_export_default_path(tmp_path, monkeypatch):
    _seed_rules()
    # Run from a temp working directory so we don't pollute the repo
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["rules", "export"])

    assert result.exit_code == 0
    assert "Exported to:" in result.output
    exported = tmp_path / "rules.py"
    assert exported.exists()
    assert "food/bakery" in exported.read_text()


def test_rules_export_custom_path(tmp_path):
    _seed_rules()
    dest = tmp_path / "my_rules.py"
    runner = CliRunner()
    result = runner.invoke(main, ["rules", "export", str(dest)])

    assert result.exit_code == 0
    assert dest.exists()
    assert "food/bakery" in dest.read_text()


def test_rules_import_saves_to_vault(tmp_path):
    config = VaultConfig()
    ensure_vault_initialized(config)

    rules_file = tmp_path / "new_rules.py"
    rules_file.write_text(SAMPLE_RULES)

    runner = CliRunner()
    result = runner.invoke(main, ["rules", "import", str(rules_file)])

    assert result.exit_code == 0
    assert "Validated: 1 rules loaded" in result.output
    assert "Rules imported successfully" in result.output

    # Verify it's now the active rules
    active = latest_rules_path(config)
    assert active is not None
    assert "food/bakery" in active.read_text()


def test_rules_import_rejects_invalid_file(tmp_path):
    config = VaultConfig()
    ensure_vault_initialized(config)

    bad_rules = tmp_path / "bad_rules.py"
    bad_rules.write_text("this is not valid python !!!")

    runner = CliRunner()
    result = runner.invoke(main, ["rules", "import", str(bad_rules)])

    assert result.exit_code != 0
    assert "Invalid rules file" in result.output
