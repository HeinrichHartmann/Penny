from penny.balance_projection import (
    build_balance_series,
    normalize_anchors,
    project_backward_with_inconsistencies,
    project_forward_from_latest_anchor,
)


def test_normalize_anchors_sorts_by_date():
    anchors = [
        {"date": "2024-01-03", "balance_cents": 300},
        {"date": "2024-01-01", "balance_cents": 100},
        {"date": "2024-01-02", "balance_cents": 200},
    ]

    normalized = normalize_anchors(anchors)

    assert [anchor["date"] for anchor in normalized] == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
    ]


def test_normalize_anchors_keeps_last_added_anchor_for_duplicate_date():
    anchors = [
        {"date": "2024-01-02", "balance_cents": 100},
        {"date": "2024-01-01", "balance_cents": 50},
        {"date": "2024-01-02", "balance_cents": 125},
    ]

    normalized = normalize_anchors(anchors)

    assert normalized == [
        {"date": "2024-01-01", "balance_cents": 50},
        {"date": "2024-01-02", "balance_cents": 125},
    ]


def test_build_balance_series_returns_empty_without_anchors():
    balances, deltas, normalized = build_balance_series(
        ["2024-01-01", "2024-01-02"],
        {"2024-01-02": 10},
        [],
    )

    assert balances == {}
    assert deltas == []
    assert normalized == []


def test_single_anchor_projects_backward_and_forward():
    balances, deltas, normalized = build_balance_series(
        ["2024-01-01", "2024-01-02", "2024-01-03"],
        {"2024-01-02": 10, "2024-01-03": -5},
        [{"date": "2024-01-02", "balance_cents": 100}],
    )

    assert normalized == [{"date": "2024-01-02", "balance_cents": 100}]
    assert balances == {
        "2024-01-01": 90,
        "2024-01-02": 100,
        "2024-01-03": 95,
    }
    assert deltas == []


def test_build_balance_series_uses_latest_anchor_for_main_projection():
    balances, deltas, normalized = build_balance_series(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        {"2024-01-02": 10, "2024-01-03": 10, "2024-01-04": 10},
        [
            {"date": "2024-01-02", "balance_cents": 100},
            {"date": "2024-01-04", "balance_cents": 150},
        ],
    )

    assert normalized == [
        {"date": "2024-01-02", "balance_cents": 100},
        {"date": "2024-01-04", "balance_cents": 150},
    ]
    assert balances == {
        "2024-01-01": 90,
        "2024-01-02": 100,
        "2024-01-03": 140,
        "2024-01-04": 150,
    }
    assert deltas == [
        {
            "date": "2024-01-02",
            "projected_balance": 130,
            "anchor_balance": 100,
            "delta_cents": -30,
        }
    ]


def test_backward_projection_records_inconsistency_at_anchor_boundary():
    balances, deltas = project_backward_with_inconsistencies(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        {"2024-01-02": 10, "2024-01-03": 10, "2024-01-04": 10},
        [
            {"date": "2024-01-02", "balance_cents": 100},
            {"date": "2024-01-04", "balance_cents": 150},
        ],
    )

    assert balances == {
        "2024-01-04": 150,
        "2024-01-03": 140,
        "2024-01-02": 100,
        "2024-01-01": 90,
    }
    assert deltas == [
        {
            "date": "2024-01-02",
            "projected_balance": 130,
            "anchor_balance": 100,
            "delta_cents": -30,
        }
    ]


def test_backward_projection_ignores_one_cent_deltas():
    _balances, deltas = project_backward_with_inconsistencies(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        {"2024-01-02": 10, "2024-01-03": 10, "2024-01-04": 10},
        [
            {"date": "2024-01-02", "balance_cents": 101},
            {"date": "2024-01-04", "balance_cents": 121},
        ],
    )

    assert deltas == []


def test_build_balance_series_fills_dates_before_first_anchor():
    balances, deltas, _normalized = build_balance_series(
        [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
        ],
        {"2024-01-02": 5, "2024-01-03": 7, "2024-01-04": 11, "2024-01-05": 13},
        [
            {"date": "2024-01-03", "balance_cents": 100},
            {"date": "2024-01-05", "balance_cents": 130},
        ],
    )

    assert balances["2024-01-01"] == 88
    assert balances["2024-01-02"] == 93
    assert balances["2024-01-03"] == 100
    assert deltas == [
        {
            "date": "2024-01-03",
            "projected_balance": 106,
            "anchor_balance": 100,
            "delta_cents": -6,
        }
    ]


def test_forward_projection_from_latest_anchor_handles_anchor_before_visible_range():
    balances = project_forward_from_latest_anchor(
        ["2024-01-03", "2024-01-04"],
        {"2024-01-03": 7, "2024-01-04": 2},
        {"date": "2024-01-01", "balance_cents": 100},
    )

    assert balances == {
        "2024-01-03": 107,
        "2024-01-04": 109,
    }


def test_build_balance_series_projects_forward_only_after_latest_anchor():
    balances, deltas, _normalized = build_balance_series(
        ["2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
        {"2024-01-04": 10, "2024-01-05": 20, "2024-01-06": -5},
        [{"date": "2024-01-04", "balance_cents": 100}],
    )

    assert balances == {
        "2024-01-03": 90,
        "2024-01-04": 100,
        "2024-01-05": 120,
        "2024-01-06": 115,
    }
    assert deltas == []


def test_build_balance_series_accepts_unsorted_anchor_input():
    balances, deltas, normalized = build_balance_series(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        {"2024-01-02": 10, "2024-01-03": 10, "2024-01-04": 10},
        [
            {"date": "2024-01-04", "balance_cents": 150},
            {"date": "2024-01-02", "balance_cents": 100},
        ],
    )

    assert normalized == [
        {"date": "2024-01-02", "balance_cents": 100},
        {"date": "2024-01-04", "balance_cents": 150},
    ]
    assert balances["2024-01-04"] == 150
    assert deltas[0]["date"] == "2024-01-02"
