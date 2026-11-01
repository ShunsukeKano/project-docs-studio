"""The generated OpenAPI document matches the design contract in specs/ (paths, methods,
operation ids and response status codes)."""

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[2]
# In the repository the contract is at ../specs; the test container mounts it at /specs.
CONTRACT = (
    BACKEND.parent / "specs" / "001-docs-studio" / "contracts" / "openapi.yaml"
    if "CONTRACT_PATH" not in os.environ
    else Path(os.environ["CONTRACT_PATH"])
)
GENERATED = BACKEND / "openapi.json"
METHODS = {"get", "post", "put", "patch", "delete"}


def operations(document: dict[str, Any], prefix_for: Any) -> dict[tuple[str, str], dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for path, item in document["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                found[(prefix_for(path), method)] = operation
    return found


def contract_path(path: str) -> str:
    # The contract's server URL is /api/v1; the liveness check lives outside it.
    return path if path == "/healthz" else f"/api/v1{path}"


@pytest.fixture(scope="module")
def contract() -> dict[tuple[str, str], dict[str, Any]]:
    return operations(yaml.safe_load(CONTRACT.read_text()), contract_path)


@pytest.fixture(scope="module")
def generated() -> dict[tuple[str, str], dict[str, Any]]:
    return operations(json.loads(GENERATED.read_text()), lambda path: path)


def test_the_same_paths_and_methods(
    contract: dict[tuple[str, str], dict[str, Any]],
    generated: dict[tuple[str, str], dict[str, Any]],
) -> None:
    assert set(generated) == set(contract)


def test_the_same_operation_ids(
    contract: dict[tuple[str, str], dict[str, Any]],
    generated: dict[tuple[str, str], dict[str, Any]],
) -> None:
    assert {k: v["operationId"] for k, v in generated.items()} == {
        k: v["operationId"] for k, v in contract.items()
    }


def test_the_same_response_status_codes(
    contract: dict[tuple[str, str], dict[str, Any]],
    generated: dict[tuple[str, str], dict[str, Any]],
) -> None:
    differences = {
        key: (sorted(generated[key]["responses"]), sorted(contract[key]["responses"]))
        for key in contract
        if set(generated[key]["responses"]) != {str(c) for c in contract[key]["responses"]}
    }
    assert differences == {}, "generated vs contract status codes differ"


def test_the_generated_file_is_what_the_app_produces_now() -> None:
    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(env="local", database_url=None, basic_auth_enabled=False))
    assert json.loads(GENERATED.read_text()) == json.loads(json.dumps(app.openapi()))
