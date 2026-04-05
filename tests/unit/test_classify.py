from penny.classify import contains, is_, load_rules, regexp


def test_match_helpers_are_case_insensitive():
    assert is_(" AMAZON ", "amazon")
    assert contains("AMAZON PAYMENTS EUROPE", "payments")
    assert regexp("Lohn / Gehalt", r"gehalt")


def test_load_rules_preserves_file_order(fixture_dir):
    ruleset = load_rules(fixture_dir / "rules_reordered.py")

    assert [rule.name for rule in ruleset.rules] == [
        "salary",
        "hotel",
        "amazon_specific",
        "amazon",
    ]
