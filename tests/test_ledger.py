import json
import os

from core import ledger


def test_load_state_returns_default_when_file_missing(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    state = ledger.load_state(path)
    assert state == ledger.DEFAULT_STATE


def test_save_then_load_roundtrips(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    custom_state = {
        "contracts_held": 15,
        "contract_year": 2026,
        "contract_month": 9,
        "equity": 201527.4,
        "last_price": 20050.0,
        "last_run_date": "2026-07-31",
    }

    ledger.save_state(path, custom_state)
    loaded = ledger.load_state(path)

    assert loaded == custom_state
    with open(path) as f:
        assert json.load(f) == custom_state


def test_apply_fill_adds_delta_and_sets_contract_month():
    result = ledger.apply_fill(contracts_held=10, delta_contracts=5, contract_year=2026, contract_month=12)
    assert result == {"contracts_held": 15, "contract_year": 2026, "contract_month": 12}


def test_apply_fill_handles_negative_delta_flattening_to_zero():
    result = ledger.apply_fill(contracts_held=15, delta_contracts=-15, contract_year=2026, contract_month=9)
    assert result == {"contracts_held": 0, "contract_year": 2026, "contract_month": 9}
