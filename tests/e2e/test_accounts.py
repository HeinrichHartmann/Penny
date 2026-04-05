from click.testing import CliRunner

from penny.cli import main


def test_accounts_cli_add_list_remove():
    runner = CliRunner()

    result = runner.invoke(main, ["accounts", "add", "comdirect", "--account-number", "9788862492"])
    assert result.exit_code == 0
    assert "Created account #1: comdirect" in result.output

    result = runner.invoke(main, ["accounts", "list"])
    assert result.exit_code == 0
    assert "comdirect" in result.output
    assert "active" in result.output

    result = runner.invoke(main, ["accounts", "remove", "1"])
    assert result.exit_code == 0
    assert "Removed account #1" in result.output

    result = runner.invoke(main, ["accounts", "list"])
    assert result.exit_code == 0
    assert "No accounts found." in result.output

    result = runner.invoke(main, ["accounts", "list", "--all"])
    assert result.exit_code == 0
    assert "hidden" in result.output
