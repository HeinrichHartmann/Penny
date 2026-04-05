import importlib.resources

from penny.classify import load_rules_config


def test_default_rules_template_loads():
    config = load_rules_config(importlib.resources.files("penny").joinpath("default_rules.py"))

    assert config.default_category == "uncategorized"
    # Default rules now include example rules for demo data
    assert len(config.ruleset.rules) > 0
    # Check a few expected rules exist
    rule_names = [r.name for r in config.ruleset.rules]
    assert "groceries" in rule_names
    assert "salary" in rule_names
    assert "bank_fees" in rule_names
