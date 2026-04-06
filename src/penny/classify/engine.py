"""Classification engine backed by Python rule modules."""

from __future__ import annotations

import importlib.util
import re
import uuid
from collections import Counter
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from penny.transactions import Transaction

Predicate = Callable[[Transaction], bool]


def _normalize_string(value: object) -> str:
    return str(value or "").strip().casefold()


def is_(value: object, expected: object) -> bool:
    """Case-insensitive equality helper."""

    return _normalize_string(value) == _normalize_string(expected)


def contains(value: object, needle: object) -> bool:
    """Case-insensitive substring helper."""

    return _normalize_string(needle) in _normalize_string(value)


def regexp(value: object, pattern: str) -> bool:
    """Case-insensitive regex search helper."""

    return re.search(pattern, str(value or ""), flags=re.IGNORECASE) is not None


@dataclass(frozen=True)
class Rule:
    """A loaded classification rule."""

    name: str
    category: str
    predicate: Predicate


@dataclass(frozen=True)
class ClassificationDecision:
    """A rule match for a specific transaction."""

    fingerprint: str
    category: str
    rule_name: str


@dataclass(frozen=True)
class RuleEvaluation:
    """Outcome of evaluating a single rule against a transaction."""

    rule_name: str
    category: str
    matched: bool
    error: str | None = None


@dataclass(frozen=True)
class LoadedRuleset:
    """An ordered set of classification rules."""

    path: Path
    rules: list[Rule]

    def classify(self, transaction: Transaction) -> ClassificationDecision | None:
        """Return the first matching decision, if any."""

        decision, _ = self.classify_with_trace(transaction)
        return decision

    def classify_with_trace(
        self,
        transaction: Transaction,
    ) -> tuple[ClassificationDecision | None, list[RuleEvaluation]]:
        """Return the first matching decision plus rule-by-rule evaluation trace."""

        evaluations: list[RuleEvaluation] = []
        for rule in self.rules:
            try:
                matched = bool(rule.predicate(transaction))
            except Exception as exc:
                evaluations.append(
                    RuleEvaluation(
                        rule_name=rule.name,
                        category=rule.category,
                        matched=False,
                        error=str(exc),
                    )
                )
                raise

            evaluations.append(
                RuleEvaluation(
                    rule_name=rule.name,
                    category=rule.category,
                    matched=matched,
                )
            )
            if matched:
                return ClassificationDecision(
                    fingerprint=transaction.fingerprint,
                    category=rule.category,
                    rule_name=rule.name,
                ), evaluations
        return None, evaluations


@dataclass(frozen=True)
class LoadedRulesConfig:
    """Ruleset plus classification defaults declared by the module."""

    ruleset: LoadedRuleset
    default_category: str
    module: ModuleType | None = None


@dataclass(frozen=True)
class ClassificationError:
    """A classification failure for an individual transaction."""

    fingerprint: str
    payee: str
    error: str


@dataclass(frozen=True)
class ClassificationPassResult:
    """Result of a full classification pass over a transaction set."""

    decisions: list[ClassificationDecision]
    matched_count: int
    default_count: int
    category_counts: Counter[str]
    defaulted_transactions: list[Transaction]
    errors: list[ClassificationError]
    traces: dict[str, list[RuleEvaluation]]


class RuleCollector:
    """Collect rules in module execution order."""

    def __init__(self, path: Path):
        self.path = path
        self.rules: list[Rule] = []

    def register(
        self, category: str, predicate: Predicate, *, name: str | None = None
    ) -> Predicate:
        rule_name = name or predicate.__name__
        self.rules.append(Rule(name=rule_name, category=category, predicate=predicate))
        return predicate

    def build(self) -> LoadedRuleset:
        return LoadedRuleset(path=self.path, rules=list(self.rules))


_ACTIVE_COLLECTOR: ContextVar[RuleCollector | None] = ContextVar(
    "penny_classification_rule_collector",
    default=None,
)


def rule(category: str, *, name: str | None = None):
    """Decorator for registering a classification rule."""

    def decorator(func: Predicate) -> Predicate:
        collector = _ACTIVE_COLLECTOR.get()
        if collector is None:
            raise RuntimeError("rule() can only be used while loading a rules module")
        collector.register(category, func, name=name)
        return func

    return decorator


def _load_module(path: Path) -> ModuleType:
    module_name = f"penny_rules_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load rules module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rules(path: Path) -> LoadedRuleset:
    """Load a rules module from disk in file order."""

    return load_rules_config(path).ruleset


def load_rules_config(path: Path) -> LoadedRulesConfig:
    """Load a rules module plus its default category."""

    collector = RuleCollector(path)
    token = _ACTIVE_COLLECTOR.set(collector)
    try:
        module = _load_module(path)
        return LoadedRulesConfig(
            ruleset=collector.build(),
            default_category=getattr(module, "DEFAULT_CATEGORY", "uncategorized"),
            module=module,
        )
    finally:
        _ACTIVE_COLLECTOR.reset(token)


def classify_transaction(
    transaction: Transaction, ruleset: LoadedRuleset
) -> ClassificationDecision | None:
    """Convenience wrapper for classifying one transaction."""

    return ruleset.classify(transaction)


def run_classification_pass(
    transactions: list[Transaction],
    config: LoadedRulesConfig,
    *,
    collect_rule_trace: bool = False,
) -> ClassificationPassResult:
    """Classify a full transaction set using the module's default category."""

    decisions: list[ClassificationDecision] = []
    category_counts: Counter[str] = Counter()
    defaulted_transactions: list[Transaction] = []
    errors: list[ClassificationError] = []
    traces: dict[str, list[RuleEvaluation]] = {}
    matched_count = 0
    default_count = 0

    for transaction in transactions:
        try:
            if collect_rule_trace:
                decision, evaluations = config.ruleset.classify_with_trace(transaction)
                traces[transaction.fingerprint] = evaluations
            else:
                decision = config.ruleset.classify(transaction)
            if decision is None:
                decision = ClassificationDecision(
                    fingerprint=transaction.fingerprint,
                    category=config.default_category,
                    rule_name="(default)",
                )
                defaulted_transactions.append(transaction)
                default_count += 1
            else:
                matched_count += 1
            decisions.append(decision)
            category_counts[decision.category] += 1
        except Exception as exc:
            errors.append(
                ClassificationError(
                    fingerprint=transaction.fingerprint,
                    payee=transaction.payee,
                    error=str(exc),
                )
            )

    return ClassificationPassResult(
        decisions=decisions,
        matched_count=matched_count,
        default_count=default_count,
        category_counts=category_counts,
        defaulted_transactions=defaulted_transactions,
        errors=errors,
        traces=traces,
    )
