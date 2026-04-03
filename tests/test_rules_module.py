from pathlib import Path

from penny.classify import load_rules


def test_root_rules_module_loads():
    ruleset = load_rules(Path(__file__).resolve().parents[1] / "rules.py")

    assert len(ruleset.rules) >= 30
    assert ruleset.rules[0].category == "salary"
