"""Rules API router."""

import importlib.resources
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from penny.classify import load_rules_config, run_classification_pass
from penny.classify.engine import LoadedRulesConfig
from penny.transactions import apply_classifications, list_transactions
from penny.vault import ensure_rules_snapshot
from penny.vault.rules import update_rules_and_apply

router = APIRouter(prefix="/api/rules", tags=["rules"])


def get_rules_path() -> Path:
    """Return the active versioned rules snapshot path."""
    return ensure_rules_snapshot()


def get_default_rules_template() -> str:
    """Read the default rules template from the package."""
    return (
        importlib.resources.files("penny").joinpath("default_rules.py").read_text(encoding="utf-8")
    )


@router.get("")
async def get_rules():
    """Get the current rules file content and path."""
    rules_path = get_rules_path()

    try:
        content = rules_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read rules file: {e}") from e

    return {
        "path": str(rules_path),
        "directory": str(rules_path.parent),
        "exists": True,
        "content": content,
        "latest_run": preview_rules_path(rules_path),
    }


class RulesUpdate(BaseModel):
    content: str


def _evaluate_rules_path(rules_path: Path, *, persist: bool) -> dict:
    """Evaluate rules for a concrete rules snapshot path."""
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

    transactions = list_transactions(limit=None, neutralize=False, include_hidden=True)
    log("info", f"Processing {len(transactions)} transactions")

    result = run_classification_pass(transactions, config)

    if persist:
        try:
            apply_classifications(result.decisions)
        except Exception as e:
            log("error", f"Failed to persist classifications: {e}", traceback=traceback.format_exc())
            return {
                "status": "error",
                "logs": logs,
                "stats": None,
            }

    if result.errors:
        log("warning", f"{len(result.errors)} errors during classification")
        for err in result.errors[:10]:
            log("error", f"Error classifying {err.payee}: {err.error}")

    log("info", f"Matched: {result.matched_count}, Unmatched: {result.default_count}")
    for category, count in sorted(result.category_counts.items()):
        log("info", f"  {category}: {count}")

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
        "started_at": start_time.isoformat(),
        "completed_at": datetime.now().isoformat(),
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


def preview_rules_path(rules_path: Path) -> dict:
    """Return the current rules evaluation result without persisting changes."""
    return _evaluate_rules_path(rules_path, persist=False)


def run_rules_path(rules_path: Path) -> dict:
    """Run classification and persist the resulting assignments."""
    return _evaluate_rules_path(rules_path, persist=True)


@router.put("")
async def save_rules(update: RulesUpdate):
    """Save rules, apply them synchronously, and return when projection is updated."""
    try:
        rules_path = update_rules_and_apply(update.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rules file: {e}") from e

    return {
        "status": "saved",
        "path": str(rules_path),
    }


@router.post("/run")
async def run_rules():
    """Run classification rules on all transactions.

    Returns stats and any errors encountered during rule loading/execution.

    This is intentionally a projection recomputation endpoint. It does not append
    anything to the vault because we audit changes to rules logic, not every
    derived classification pass.
    """
    rules_path = get_rules_path()

    # Check if rules file exists
    if not rules_path.exists():
        return {
            "status": "error",
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "logs": [
                {
                    "level": "error",
                    "message": f"Rules file not found: {rules_path}",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
            "stats": None,
        }
    return run_rules_path(rules_path)
