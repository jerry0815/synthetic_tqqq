import json
import os

DEFAULT_STATE = {
    "contracts_held": 0,
    "contract_year": None,
    "contract_month": None,
    "equity": 200000.0,
    "last_price": None,
    "last_run_date": None,
}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return dict(DEFAULT_STATE)
    with open(path, "r") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def apply_fill(contracts_held: int, delta_contracts: int, contract_year: int, contract_month: int) -> dict:
    """Return the position fields after applying a fill of delta_contracts,
    now held under the given contract month."""
    return {
        "contracts_held": contracts_held + delta_contracts,
        "contract_year": contract_year,
        "contract_month": contract_month,
    }
