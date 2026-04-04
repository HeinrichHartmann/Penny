from click.testing import CliRunner

from penny.cli import main


def test_top_level_help_lists_serve_and_apply():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "apply" in result.output
    assert "db" in result.output
    assert "log" in result.output
    assert "serve" in result.output


def test_serve_help_lists_host_and_port():
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
