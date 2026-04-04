"""Rules API router."""

import importlib.resources
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from penny.accounts.storage import default_db_path
from penny.classify import load_rules_config, run_classification_pass
from penny.classify.engine import LoadedRulesConfig
from penny.transactions.storage import TransactionStorage

router = APIRouter(prefix="/api/rules", tags=["rules"])


def get_rules_path() -> Path:
    """Get the rules file path in the XDG data directory."""
    # Always use the XDG data directory (same as penny.db)
    data_dir = default_db_path().parent
    return data_dir / "rules.py"


def get_default_rules_template() -> str:
    """Read the default rules template from the package."""
    return importlib.resources.files("penny").joinpath("default_rules.py").read_text(encoding="utf-8")


@router.get("")
async def get_rules():
    """Get the current rules file content and path."""
    rules_path = get_rules_path()

    if not rules_path.exists():
        # Create minimal template
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(get_default_rules_template(), encoding="utf-8")
        return {
            "path": str(rules_path),
            "directory": str(rules_path.parent),
            "exists": True,
            "content": get_default_rules_template(),
            "created": True,
        }

    try:
        content = rules_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read rules file: {e}")

    return {
        "path": str(rules_path),
        "directory": str(rules_path.parent),
        "exists": True,
        "content": content,
    }


class RulesUpdate(BaseModel):
    content: str


@router.put("")
async def save_rules(update: RulesUpdate):
    """Save the rules file content."""
    rules_path = get_rules_path()

    # Ensure directory exists
    rules_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        rules_path.write_text(update.content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rules file: {e}")

    return {
        "status": "saved",
        "path": str(rules_path),
    }


@router.post("/run")
async def run_rules():
    """Run classification rules on all transactions.

    Returns stats and any errors encountered during rule loading/execution.
    """
    rules_path = get_rules_path()
    logs: list[dict] = []
    start_time = datetime.now()

    def log(level: str, message: str, **extra):
        logs.append(
            {
                "level": level,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                **extra,
            }
        )

    # Check if rules file exists
    if not rules_path.exists():
        log("error", f"Rules file not found: {rules_path}")
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }

    # Load rules
    config: LoadedRulesConfig | None = None
    try:
        log("info", f"Loading rules from {rules_path}")
        config = load_rules_config(rules_path)
        log("info", f"Loaded {len(config.ruleset.rules)} rules")
        log("info", f"Default category: {config.default_category}")
        for rule in config.ruleset.rules:
            log("debug", f"  - {rule.name} -> {rule.category}")
    except SyntaxError as e:
        log("error", f"Syntax error in rules file: {e.msg}", line=e.lineno, offset=e.offset)
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }
    except Exception as e:
        log("error", f"Failed to load rules: {e}", traceback=traceback.format_exc())
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }

    # Get all transactions
    tx_storage = TransactionStorage()
    transactions = tx_storage.list_transactions(limit=None, consolidated=False)
    log("info", f"Processing {len(transactions)} transactions")

    result = run_classification_pass(transactions, config)

    try:
        tx_storage.apply_classifications(result.decisions)
    except Exception as e:
        log("error", f"Failed to persist classifications: {e}", traceback=traceback.format_exc())
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }

    # Log classification errors
    if result.errors:
        log("warning", f"{len(result.errors)} errors during classification")
        for err in result.errors[:10]:  # Show first 10
            log("error", f"Error classifying {err.payee}: {err.error}")

    # Log category breakdown
    log("info", f"Matched: {result.matched_count}, Unmatched: {result.default_count}")
    for category, count in sorted(result.category_counts.items()):
        log("info", f"  {category}: {count}")

    # Log largest unmatched transactions (top 30 by absolute amount)
    if result.defaulted_transactions:
        log("warning", "Top unmatched transactions (by amount):")
        sorted_unmatched = sorted(
            result.defaulted_transactions,
            key=lambda t: abs(t.amount_cents),
            reverse=True,
        )[:30]
        for tx in sorted_unmatched:
            amount_eur = tx.amount_cents / 100
            log("warning", f"  {amount_eur:>10.2f} EUR | {tx.date} | {tx.payee[:40]}")

    elapsed = (datetime.now() - start_time).total_seconds()
    log("info", f"Classification completed in {elapsed:.2f}s")

    return {
        "status": "success",
        "logs": logs,
        "stats": {
            "rules_count": len(config.ruleset.rules),
            "transactions_count": len(transactions),
            "matched_count": result.matched_count,
            "unmatched_count": result.default_count,
            "categories": [
                {"category": cat, "count": count}
                for cat, count in sorted(result.category_counts.items())
            ],
            "elapsed_seconds": elapsed,
        },
    }
