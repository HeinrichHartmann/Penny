import importlib.resources

from penny.classify import load_rules_config


def test_default_rules_template_loads():
    config = load_rules_config(importlib.resources.files("penny").joinpath("default_rules.py"))

    assert config.default_category == "uncategorized"
    assert config.ruleset.rules == []
