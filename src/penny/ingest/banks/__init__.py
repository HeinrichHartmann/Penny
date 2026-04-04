"""Bank modules - one per supported bank."""

from penny.ingest.banks.comdirect import ComdirectBank
from penny.ingest.banks.sparkasse import SparkasseBank

BANKS = [ComdirectBank(), SparkasseBank()]


def get_banks() -> list:
    """Return all registered bank modules."""
    return BANKS
