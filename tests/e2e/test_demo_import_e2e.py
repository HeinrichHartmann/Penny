"""End-to-end test for demo data import flow.

Tests the complete user journey:
1. Fresh vault (empty)
2. Import demo files (CSV, rules.py, balance-anchors.tsv)
3. Verify data appears in all views (Transactions, Report, Balance)
"""

import pytest
from fastapi.testclient import TestClient

from penny.server import app


@pytest.mark.integration
def test_demo_import_end_to_end():
    """Test complete demo import flow via API endpoints."""
    with TestClient(app) as client:
        # Step 1: Verify fresh vault is empty
        meta_response = client.get("/api/meta")
        assert meta_response.status_code == 200
        meta = meta_response.json()
        assert meta["accounts"] == []
        assert meta["min_date"] is None
        assert meta["max_date"] is None

        imports_response = client.get("/api/imports")
        assert imports_response.status_code == 200
        assert imports_response.json()["imports"] == []

        # Step 2: Get demo files list
        demo_files_response = client.get("/api/demo-files")
        assert demo_files_response.status_code == 200
        demo_files = demo_files_response.json()["files"]
        assert len(demo_files) == 3

        # Verify expected files are present
        filenames = [f["filename"] for f in demo_files]
        assert any("CSV" in name or "csv" in name for name in filenames), "Demo CSV not found"
        assert "demo_rules.py" in filenames, "Demo rules not found"
        assert "balance-anchors.tsv" in filenames, "Balance anchors TSV not found"

        # Step 3: Download and import each demo file
        import_results = []
        for file_info in demo_files:
            filename = file_info["filename"]

            download_response = client.get(f"/api/demo-files/{filename}")
            assert download_response.status_code == 200, f"Failed to download {filename}"

            files = {"file": (filename, download_response.content)}
            import_response = client.post("/api/import", files=files)
            assert import_response.status_code == 200, f"Failed to import {filename}"

            result = import_response.json()
            import_results.append(result)
            print(f"✓ Imported {filename}: {result['type']}")

        # Step 4: Verify imports appear in history
        imports_history_response = client.get("/api/imports")
        assert imports_history_response.status_code == 200
        imports_history = imports_history_response.json()["imports"]

        print(f"\n📋 Import history ({len(imports_history)} entries):")
        for imp in imports_history:
            print(f"   - {imp['type']}: {imp['filenames']}")

        import_types = [imp["type"] for imp in imports_history]
        assert "csv" in import_types or "ingest" in import_types, "CSV import not in history"
        assert "rules" in import_types, "Rules import not in history"

        if "balance_anchors" not in import_types:
            print("⚠️  Balance anchors not in import history (checking vault entries instead)")

        # Step 5: Verify meta now has data
        meta_after = client.get("/api/meta").json()
        assert len(meta_after["accounts"]) > 0, "No accounts created"
        assert meta_after["min_date"] is not None, "min_date still null"
        assert meta_after["max_date"] is not None, "max_date still null"
        assert meta_after["min_date"] == "2022-04-01", (
            f"Unexpected min_date: {meta_after['min_date']}"
        )
        assert meta_after["max_date"] == "2024-03-29", (
            f"Unexpected max_date: {meta_after['max_date']}"
        )

        print(
            f"✓ Meta: {len(meta_after['accounts'])} account(s), "
            f"date range: {meta_after['min_date']} to {meta_after['max_date']}"
        )

        account_ids = ",".join(str(acc["id"]) for acc in meta_after["accounts"])

        # Step 6: Verify transactions are present
        transactions_response = client.get(
            "/api/transactions",
            params={
                "from": meta_after["min_date"],
                "to": meta_after["max_date"],
                "accounts": account_ids,
                "neutralize": "true",
            },
        )
        assert transactions_response.status_code == 200
        transactions_data = transactions_response.json()
        assert transactions_data["count"] > 0, "No transactions found after import"
        assert transactions_data["count"] == 864, (
            f"Expected 864 transactions, got {transactions_data['count']}"
        )

        print(f"✓ Transactions: {transactions_data['count']} transaction(s)")

        # Step 7: Verify summary and pivot data for the report views
        summary_response = client.get(
            "/api/summary",
            params={
                "from": meta_after["min_date"],
                "to": meta_after["max_date"],
                "accounts": account_ids,
            },
        )
        assert summary_response.status_code == 200
        summary_data = summary_response.json()
        assert summary_data["expense"]["count"] > 0, "No expenses in summary"
        assert summary_data["expense"]["total_cents"] < 0, "Expense total should be negative"

        pivot_response = client.get(
            "/api/pivot",
            params={
                "from": meta_after["min_date"],
                "to": meta_after["max_date"],
                "accounts": account_ids,
                "tab": "expense",
                "depth": "1",
            },
        )
        assert pivot_response.status_code == 200
        pivot_data = pivot_response.json()
        assert pivot_data["total_cents"] > 0, "No expenses in pivot"
        assert len(pivot_data["categories"]) > 0, "No categories in pivot"

        print(
            f"✓ Report: {len(pivot_data['categories'])} category/categories, "
            f"total: €{pivot_data['total_cents']/100:.2f}"
        )

        # Step 8: Verify balance history with anchors
        balance_response = client.get(f"/api/account_value_history?accounts={account_ids}")
        assert balance_response.status_code == 200
        balance_data = balance_response.json()

        assert len(balance_data["value_points"]) > 0, "No balance value points"
        assert len(balance_data["balance_snapshots"]) == 5, (
            f"Expected 5 balance snapshots, got {len(balance_data['balance_snapshots'])}"
        )

        anchor_points = [vp for vp in balance_data["value_points"] if vp.get("is_anchor")]
        assert len(anchor_points) == 5, f"Expected 5 anchor points, got {len(anchor_points)}"

        print(
            f"✓ Balance: {len(balance_data['value_points'])} value points, "
            f"{len(anchor_points)} anchors, "
            f"{len(balance_data.get('inconsistencies', []))} inconsistencies"
        )

        # Step 9: Verify classifications were applied (rules.py was imported)
        classified_txs = [tx for tx in transactions_data["transactions"] if tx.get("category")]
        assert len(classified_txs) > 0, "No transactions were classified by rules"

        print(
            f"✓ Classifications: {len(classified_txs)}/{transactions_data['count']} "
            f"transactions classified"
        )

        print("\n✅ End-to-end demo import test PASSED")
