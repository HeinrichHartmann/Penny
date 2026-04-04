"""Generate demo account and sample transaction data for new users.

This module creates realistic sample data spanning ~2 years with ~1000 transactions
across multiple categories (groceries, rent, salary, utilities, etc.).
"""

from __future__ import annotations

import random
from datetime import date, timedelta

# Transaction templates with realistic patterns
TRANSACTION_TEMPLATES = {
    "salary": {
        "frequency": "monthly",
        "day_of_month": 28,
        "payee": "Demo Employer GmbH",
        "iban": "DE12500105170123456789",
        "bic": "INGDDEFF",
        "amount_range": (2800.00, 3200.00),
        "buchungstext": "GUTSCHRIFT UEBERWEISUNG",
        "verwendungszweck": "Gehalt {month} {year}",
        "reference": "SALARY-{year}-{month:02d}",
    },
    "rent": {
        "frequency": "monthly",
        "day_of_month": 1,
        "payee": "Hausverwaltung Muster",
        "iban": "DE98765432109876543210",
        "bic": "COBADEFF",
        "amount_range": (-950.00, -950.00),
        "buchungstext": "ONLINE-UEBERWEISUNG",
        "verwendungszweck": "Miete {month_name}",
        "reference": "RENT-{year}-{month:02d}",
    },
    "electricity": {
        "frequency": "monthly",
        "day_of_month": 15,
        "payee": "Stadtwerke Demo",
        "iban": "DE11223344556677889900",
        "bic": "SWDEFF",
        "amount_range": (-65.00, -95.00),
        "buchungstext": "SEPA-LASTSCHRIFT",
        "verwendungszweck": "Stromabschlag {month}/{year}",
        "reference": "ELEC-{year}-{month:02d}",
        "glaeubiger_id": "DE98ZZZ09999999999",
        "mandatsreferenz": "MREF1234567890",
    },
    "internet": {
        "frequency": "monthly",
        "day_of_month": 5,
        "payee": "Telekom Deutschland GmbH",
        "iban": "DE55667788990011223344",
        "bic": "TELKDEFF",
        "amount_range": (-44.99, -44.99),
        "buchungstext": "SEPA-LASTSCHRIFT",
        "verwendungszweck": "DSL/Telefon Rechnung",
        "reference": "TEL-{year}-{month:02d}",
        "glaeubiger_id": "DE77ZZZ01234567890",
        "mandatsreferenz": "MREF0987654321",
    },
    "insurance": {
        "frequency": "monthly",
        "day_of_month": 10,
        "payee": "Versicherung Demo AG",
        "iban": "DE66778899001122334455",
        "bic": "VERSEFF",
        "amount_range": (-125.00, -125.00),
        "buchungstext": "SEPA-LASTSCHRIFT",
        "verwendungszweck": "Versicherungsbeitrag",
        "reference": "INS-{year}-{month:02d}",
        "glaeubiger_id": "DE66ZZZ11223344556677",
        "mandatsreferenz": "MREF1122334455",
    },
    "grocery": {
        "frequency": "variable",
        "times_per_month": (8, 12),
        "payees": [
            "REWE",
            "EDEKA",
            "ALDI SÜD",
            "LIDL",
            "Kaufland",
            "DM-Drogerie",
            "ROSSMANN",
        ],
        "amount_range": (-8.50, -85.00),
        "buchungstext": "KARTENZAHLUNG",
        "verwendungszweck": "Kartenzahlung {payee}",
    },
    "restaurant": {
        "frequency": "variable",
        "times_per_month": (3, 8),
        "payees": [
            "Restaurant Bella Italia",
            "Café Central",
            "Burger King",
            "McDonald's",
            "Asia Wok",
            "Pizzeria Roma",
            "Bäckerei Schmidt",
        ],
        "amount_range": (-6.50, -45.00),
        "buchungstext": "KARTENZAHLUNG",
        "verwendungszweck": "Kartenzahlung {payee}",
    },
    "online_shopping": {
        "frequency": "variable",
        "times_per_month": (2, 6),
        "payees": [
            "Amazon EU S.a.r.L",
            "PayPal Europe",
            "Zalando SE",
            "eBay GmbH",
            "Otto GmbH",
        ],
        "amount_range": (-15.00, -120.00),
        "buchungstext": "LASTSCHRIFT / BELASTUNG",
        "verwendungszweck": "Online-Bestellung {reference}",
        "reference_pattern": "ORDER-{random:10}",
    },
    "atm_withdrawal": {
        "frequency": "variable",
        "times_per_month": (2, 4),
        "payee": "Geldautomat",
        "amount_range": (-50.00, -200.00),
        "buchungstext": "BARGELDAUSZAHLUNG",
        "verwendungszweck": "Bargeldauszahlung GA {random:6}",
    },
    "gas_station": {
        "frequency": "variable",
        "times_per_month": (3, 6),
        "payees": ["Shell", "Aral", "ESSO", "JET Tankstelle", "Total"],
        "amount_range": (-35.00, -75.00),
        "buchungstext": "KARTENZAHLUNG",
        "verwendungszweck": "Kartenzahlung {payee}",
    },
    "subscription": {
        "frequency": "monthly",
        "day_of_month": 20,
        "payees_monthly": [
            {"name": "Spotify AB", "amount": -9.99, "ref": "SPOTIFY"},
            {"name": "Netflix International", "amount": -12.99, "ref": "NETFLIX"},
            {"name": "Fitness Studio", "amount": -29.90, "ref": "GYM"},
        ],
        "buchungstext": "SEPA-LASTSCHRIFT",
        "verwendungszweck": "{name} Mitgliedschaft",
    },
    "savings_transfer": {
        "frequency": "monthly",
        "day_of_month": 29,
        "payee": "Eigene Überweisung",
        "amount_range": (-200.00, -500.00),
        "buchungstext": "ONLINE-UEBERWEISUNG",
        "verwendungszweck": "Sparen",
        "reference": "SAVINGS-{year}-{month:02d}",
    },
    "account_fee": {
        "frequency": "quarterly",
        "month_offset": [1, 4, 7, 10],
        "day_of_month": 1,
        "payee": "",
        "amount_range": (-9.90, -9.90),
        "buchungstext": "ENTGELTABSCHLUSS",
        "verwendungszweck": "Kontoführung {month_name}",
    },
}

MONTH_NAMES = [
    "Januar",
    "Februar",
    "Maerz",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]


def generate_demo_csv(
    start_date: date | None = None,
    end_date: date | None = None,
    account_number: str = "12345678",
    iban: str = "DE89370400440532013000",
) -> str:
    """Generate a realistic demo CSV in Sparkasse CAMT v8 format.

    Args:
        start_date: Start date for transactions (default: 2 years ago)
        end_date: End date for transactions (default: today)
        account_number: Account number for filename
        iban: IBAN for the demo account

    Returns:
        CSV content as string
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=730)  # 2 years ago
    if end_date is None:
        end_date = date.today()

    transactions = []

    # Generate monthly recurring transactions
    current = start_date
    while current <= end_date:
        year = current.year
        month = current.month
        month_name = MONTH_NAMES[month - 1]

        # Salary
        if "salary" in TRANSACTION_TEMPLATES:
            tmpl = TRANSACTION_TEMPLATES["salary"]
            tx_date = date(year, month, min(tmpl["day_of_month"], 28))
            if start_date <= tx_date <= end_date:
                amount = round(random.uniform(*tmpl["amount_range"]), 2)
                transactions.append(
                    {
                        "date": tx_date,
                        "auftragskonto": iban,
                        "buchungstag": tx_date.strftime("%d.%m.%y"),
                        "valutadatum": tx_date.strftime("%d.%m.%y"),
                        "buchungstext": tmpl["buchungstext"],
                        "verwendungszweck": tmpl["verwendungszweck"].format(
                            month=month_name, year=year
                        ),
                        "glaeubiger_id": "",
                        "mandatsreferenz": "",
                        "kundenreferenz": tmpl["reference"].format(year=year, month=month),
                        "sammlerreferenz": "",
                        "lastschrift_ursprungsbetrag": "",
                        "auslagenersatz": "",
                        "beguenstigter": tmpl["payee"],
                        "kontonummer_iban": tmpl["iban"],
                        "bic": tmpl["bic"],
                        "betrag": f"{amount:.2f}",
                        "waehrung": "EUR",
                        "info": "Umsatz gebucht",
                    }
                )

        # Rent
        if "rent" in TRANSACTION_TEMPLATES:
            tmpl = TRANSACTION_TEMPLATES["rent"]
            tx_date = date(year, month, tmpl["day_of_month"])
            if start_date <= tx_date <= end_date:
                amount = tmpl["amount_range"][0]
                transactions.append(
                    {
                        "date": tx_date,
                        "auftragskonto": iban,
                        "buchungstag": tx_date.strftime("%d.%m.%y"),
                        "valutadatum": tx_date.strftime("%d.%m.%y"),
                        "buchungstext": tmpl["buchungstext"],
                        "verwendungszweck": tmpl["verwendungszweck"].format(month_name=month_name),
                        "glaeubiger_id": "",
                        "mandatsreferenz": "",
                        "kundenreferenz": tmpl["reference"].format(year=year, month=month),
                        "sammlerreferenz": "",
                        "lastschrift_ursprungsbetrag": "",
                        "auslagenersatz": "",
                        "beguenstigter": tmpl["payee"],
                        "kontonummer_iban": tmpl["iban"],
                        "bic": tmpl["bic"],
                        "betrag": f"{amount:.2f}",
                        "waehrung": "EUR",
                        "info": "Umsatz gebucht",
                    }
                )

        # Utilities
        for util_type in ["electricity", "internet", "insurance"]:
            if util_type in TRANSACTION_TEMPLATES:
                tmpl = TRANSACTION_TEMPLATES[util_type]
                try:
                    tx_date = date(year, month, tmpl["day_of_month"])
                except ValueError:
                    # Handle months with fewer days
                    tx_date = date(year, month, 28)
                if start_date <= tx_date <= end_date:
                    amount = round(random.uniform(*tmpl["amount_range"]), 2)
                    transactions.append(
                        {
                            "date": tx_date,
                            "auftragskonto": iban,
                            "buchungstag": tx_date.strftime("%d.%m.%y"),
                            "valutadatum": tx_date.strftime("%d.%m.%y"),
                            "buchungstext": tmpl["buchungstext"],
                            "verwendungszweck": tmpl["verwendungszweck"].format(
                                month=month, year=year, month_name=month_name
                            ),
                            "glaeubiger_id": tmpl.get("glaeubiger_id", ""),
                            "mandatsreferenz": tmpl.get("mandatsreferenz", ""),
                            "kundenreferenz": tmpl.get("reference", "").format(
                                year=year, month=month
                            ),
                            "sammlerreferenz": "",
                            "lastschrift_ursprungsbetrag": "",
                            "auslagenersatz": "",
                            "beguenstigter": tmpl["payee"],
                            "kontonummer_iban": tmpl["iban"],
                            "bic": tmpl["bic"],
                            "betrag": f"{amount:.2f}",
                            "waehrung": "EUR",
                            "info": "Umsatz gebucht",
                        }
                    )

        # Subscriptions
        if "subscription" in TRANSACTION_TEMPLATES:
            tmpl = TRANSACTION_TEMPLATES["subscription"]
            tx_date = date(year, month, min(tmpl["day_of_month"], 28))
            if start_date <= tx_date <= end_date:
                for sub in tmpl["payees_monthly"]:
                    transactions.append(
                        {
                            "date": tx_date,
                            "auftragskonto": iban,
                            "buchungstag": tx_date.strftime("%d.%m.%y"),
                            "valutadatum": tx_date.strftime("%d.%m.%y"),
                            "buchungstext": tmpl["buchungstext"],
                            "verwendungszweck": tmpl["verwendungszweck"].format(name=sub["name"]),
                            "glaeubiger_id": "",
                            "mandatsreferenz": "",
                            "kundenreferenz": sub["ref"] + f"-{year}-{month:02d}",
                            "sammlerreferenz": "",
                            "lastschrift_ursprungsbetrag": "",
                            "auslagenersatz": "",
                            "beguenstigter": sub["name"],
                            "kontonummer_iban": "",
                            "bic": "",
                            "betrag": f"{sub['amount']:.2f}",
                            "waehrung": "EUR",
                            "info": "Umsatz gebucht",
                        }
                    )

        # Savings transfer
        if "savings_transfer" in TRANSACTION_TEMPLATES:
            tmpl = TRANSACTION_TEMPLATES["savings_transfer"]
            try:
                tx_date = date(year, month, tmpl["day_of_month"])
            except ValueError:
                tx_date = date(year, month, 28)
            if start_date <= tx_date <= end_date:
                amount = round(random.uniform(*tmpl["amount_range"]), 2)
                transactions.append(
                    {
                        "date": tx_date,
                        "auftragskonto": iban,
                        "buchungstag": tx_date.strftime("%d.%m.%y"),
                        "valutadatum": tx_date.strftime("%d.%m.%y"),
                        "buchungstext": tmpl["buchungstext"],
                        "verwendungszweck": tmpl["verwendungszweck"],
                        "glaeubiger_id": "",
                        "mandatsreferenz": "",
                        "kundenreferenz": tmpl["reference"].format(year=year, month=month),
                        "sammlerreferenz": "",
                        "lastschrift_ursprungsbetrag": "",
                        "auslagenersatz": "",
                        "beguenstigter": tmpl["payee"],
                        "kontonummer_iban": "",
                        "bic": "",
                        "betrag": f"{amount:.2f}",
                        "waehrung": "EUR",
                        "info": "Umsatz gebucht",
                    }
                )

        # Quarterly account fees
        if "account_fee" in TRANSACTION_TEMPLATES:
            tmpl = TRANSACTION_TEMPLATES["account_fee"]
            if month in tmpl["month_offset"]:
                tx_date = date(year, month, tmpl["day_of_month"])
                if start_date <= tx_date <= end_date:
                    amount = tmpl["amount_range"][0]
                    transactions.append(
                        {
                            "date": tx_date,
                            "auftragskonto": iban,
                            "buchungstag": tx_date.strftime("%d.%m.%y"),
                            "valutadatum": tx_date.strftime("%d.%m.%y"),
                            "buchungstext": tmpl["buchungstext"],
                            "verwendungszweck": tmpl["verwendungszweck"].format(
                                month_name=month_name
                            ),
                            "glaeubiger_id": "",
                            "mandatsreferenz": "",
                            "kundenreferenz": "",
                            "sammlerreferenz": "",
                            "lastschrift_ursprungsbetrag": "",
                            "auslagenersatz": "",
                            "beguenstigter": "",
                            "kontonummer_iban": "",
                            "bic": "",
                            "betrag": f"{amount:.2f}",
                            "waehrung": "EUR",
                            "info": "Umsatz gebucht",
                        }
                    )

        # Variable transactions (groceries, restaurants, etc.)
        for var_type in [
            "grocery",
            "restaurant",
            "online_shopping",
            "atm_withdrawal",
            "gas_station",
        ]:
            if var_type in TRANSACTION_TEMPLATES:
                tmpl = TRANSACTION_TEMPLATES[var_type]
                num_transactions = random.randint(*tmpl["times_per_month"])

                for _ in range(num_transactions):
                    # Random day in month
                    day = random.randint(1, 28)
                    try:
                        tx_date = date(year, month, day)
                    except ValueError:
                        continue

                    if not (start_date <= tx_date <= end_date):
                        continue

                    amount = round(random.uniform(*tmpl["amount_range"]), 2)

                    if "payees" in tmpl:
                        payee = random.choice(tmpl["payees"])
                    else:
                        payee = tmpl.get("payee", "")

                    verwendungszweck = tmpl["verwendungszweck"].format(
                        payee=payee,
                        reference=f"{random.randint(100000, 999999)}",
                        random=f"{random.randint(100000, 999999)}",
                    )

                    transactions.append(
                        {
                            "date": tx_date,
                            "auftragskonto": iban,
                            "buchungstag": tx_date.strftime("%d.%m.%y"),
                            "valutadatum": tx_date.strftime("%d.%m.%y"),
                            "buchungstext": tmpl["buchungstext"],
                            "verwendungszweck": verwendungszweck,
                            "glaeubiger_id": "",
                            "mandatsreferenz": "",
                            "kundenreferenz": "",
                            "sammlerreferenz": "",
                            "lastschrift_ursprungsbetrag": "",
                            "auslagenersatz": "",
                            "beguenstigter": payee,
                            "kontonummer_iban": "",
                            "bic": "",
                            "betrag": f"{amount:.2f}",
                            "waehrung": "EUR",
                            "info": "Umsatz gebucht",
                        }
                    )

        # Move to next month
        if month == 12:
            current = date(year + 1, 1, 1)
        else:
            current = date(year, month + 1, 1)

    # Sort transactions by date (newest first for realistic bank exports)
    transactions.sort(key=lambda x: x["date"], reverse=True)

    # Generate CSV
    header = '"Auftragskonto";"Buchungstag";"Valutadatum";"Buchungstext";"Verwendungszweck";"Glaeubiger ID";"Mandatsreferenz";"Kundenreferenz (End-to-End)";"Sammlerreferenz";"Lastschrift Ursprungsbetrag";"Auslagenersatz Ruecklastschrift";"Beguenstigter/Zahlungspflichtiger";"Kontonummer/IBAN";"BIC (SWIFT-Code)";"Betrag";"Waehrung";"Info"\n'

    rows = []
    for tx in transactions:
        row = (
            f'"{tx["auftragskonto"]}";'
            f'"{tx["buchungstag"]}";'
            f'"{tx["valutadatum"]}";'
            f'"{tx["buchungstext"]}";'
            f'"{tx["verwendungszweck"]}";'
            f'"{tx["glaeubiger_id"]}";'
            f'"{tx["mandatsreferenz"]}";'
            f'"{tx["kundenreferenz"]}";'
            f'"{tx["sammlerreferenz"]}";'
            f'"{tx["lastschrift_ursprungsbetrag"]}";'
            f'"{tx["auslagenersatz"]}";'
            f'"{tx["beguenstigter"]}";'
            f'"{tx["kontonummer_iban"]}";'
            f'"{tx["bic"]}";'
            f'"{tx["betrag"]}";'
            f'"{tx["waehrung"]}";'
            f'"{tx["info"]}"\n'
        )
        rows.append(row)

    return header + "".join(rows)


def get_demo_filename() -> str:
    """Generate a filename for the demo CSV in Sparkasse format."""
    today = date.today()
    return f"{today.strftime('%Y%m%d')}-12345678-umsatz-camt52v8.CSV"
