#!/usr/bin/env python3
"""Generate demo data snapshot for Penny.

Run this script once to create the demo CSV file that will be shipped with the project.
"""

from datetime import date, timedelta
from pathlib import Path

from penny.demo_data import generate_demo_csv, get_demo_filename


def main():
    """Generate and save demo data snapshot."""
    # Generate data for the last 2 years
    end_date = date(2024, 3, 31)  # Fixed date for reproducibility
    start_date = end_date - timedelta(days=730)  # ~2 years

    print(f"Generating demo data from {start_date} to {end_date}...")

    csv_content = generate_demo_csv(
        start_date=start_date,
        end_date=end_date,
        account_number="12345678",
        iban="DE89370400440532013000",
    )

    # Save to fixtures directory
    fixtures_dir = Path(__file__).parent.parent / "src" / "penny" / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    output_file = fixtures_dir / get_demo_filename()
    output_file.write_text(csv_content, encoding="utf-8")

    # Count transactions
    num_transactions = csv_content.count('\n') - 1  # Subtract header

    print(f"✓ Generated {num_transactions} transactions")
    print(f"✓ Saved to: {output_file}")
    print(f"\nFile size: {output_file.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
