from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.registry import (
    MAX_DOCUMENT_BYTES,
    DatasetRegistry,
    DocumentRegistry,
    ReportStore,
    sanitise_filename,
)
from api.settings import Settings, require_api_key
from memory.sqlite_store import SQLiteConversationStore
from orchestrator.llm_gateway import LLMGateway
from orchestrator.orchestrator import Orchestrator


API_KEY = "test-secret-key"
AUTH = {"X-API-Key": API_KEY}

DATASET_PATH = "data/sample_sales.xlsx"


# ========================================================
# STUB GATEWAY
# ========================================================


def make_response(**overrides) -> dict:
    payload = {
        "answer": "stub answer",
        "analysis_type": "general",
        "datasets_used": [],
        "calculations_performed": [],
        "key_findings": [],
        "sources": [],
        "confidence": 0.5,
    }

    payload.update(overrides)

    return payload


class StubGateway:
    """
    No provider, no API key, no network.

    Constructing the gateway directly is what proves the
    app depends on injection rather than on configuration.
    """

    def __init__(self, plan=None, response=None):
        self.plan = plan or {
            "steps": [
                {
                    "tool": "aggregate_dataset",
                    "arguments": {
                        "column": "Revenue",
                        "operation": "sum",
                    },
                }
            ]
        }

        self.response = response or make_response()

        self.structured_calls: list = []

    def as_gateway(self) -> LLMGateway:
        return LLMGateway(
            provider="stub",
            raw_function=lambda messages: json.dumps(
                self.plan
            ),
            structured_function=self.structured,
        )

    def structured(self, messages):
        self.structured_calls.append(messages)
        return dict(self.response)


@pytest.fixture(autouse=True)
def isolated_charts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "data_analysis.charts.DEFAULT_OUTPUT_DIRECTORY",
        tmp_path,
    )


@pytest.fixture(autouse=True)
def no_retrieval(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.orchestrator.retrieve_relevant_chunks",
        lambda question, **kwargs: [],
    )


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        provider="stub",
        api_key=API_KEY,
        dataset_path=DATASET_PATH,
        analytics_database_path="data/sales.db",
        chat_database_url=(
            "sqlite:///"
            + str(
                tmp_path / "chat.db"
            ).replace("\\", "/")
        ),
        documents_directory=str(
            tmp_path / "documents"
        ),
        dataset_upload_directory=str(
            tmp_path / "uploads"
        ),
        allowed_origins=("http://localhost:4200",),
    )


@pytest.fixture
def stub() -> StubGateway:
    return StubGateway()


@pytest.fixture
def client(settings, stub) -> TestClient:
    orchestrator = Orchestrator(
        gateway=stub.as_gateway(),
        dataset_path=settings.dataset_path,
    )

    return TestClient(
        create_app(
            settings=settings,
            orchestrator=orchestrator,
        )
    )


@pytest.fixture
def anon_client(settings, stub) -> TestClient:
    orchestrator = Orchestrator(
        gateway=stub.as_gateway(),
        dataset_path=settings.dataset_path,
    )

    return TestClient(
        create_app(
            settings=settings,
            orchestrator=orchestrator,
        ),
        headers={},
    )


# ========================================================
# AUTH
# ========================================================


def test_health_needs_no_key(client):
    response = client.get("/health")

    assert response.status_code == 200


def test_chat_without_key_is_rejected(client):
    response = client.post(
        "/chat",
        json={
            "session_id": "s1",
            "message": "hello",
        },
    )

    assert response.status_code == 401


def test_chat_with_wrong_key_is_rejected(client):
    response = client.post(
        "/chat",
        headers={"X-API-Key": "wrong"},
        json={
            "session_id": "s1",
            "message": "hello",
        },
    )

    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_missing_key_message_names_the_header(client):
    response = client.post(
        "/chat",
        json={
            "session_id": "s1",
            "message": "hello",
        },
    )

    assert "X-API-Key" in response.json()["detail"]


def test_sessions_require_a_key(client):
    assert client.get("/sessions").status_code == 401


def test_datasets_require_a_key(client):
    assert client.get("/datasets").status_code == 401


def test_documents_require_a_key(client):
    assert client.get("/documents").status_code == 401


def test_delete_requires_a_key(client):
    assert (
        client.delete("/sessions/s1").status_code
        == 401
    )


def test_refuses_to_start_without_a_key():
    with pytest.raises(RuntimeError):
        require_api_key(Settings(api_key=None))


def test_require_api_key_returns_the_key():
    assert (
        require_api_key(Settings(api_key="abc"))
        == "abc"
    )


# ========================================================
# HEALTH
# ========================================================


def test_health_reports_engine_state(client):
    payload = client.get("/health").json()

    assert payload["status"] == "ok"
    assert payload["provider"] == "stub"
    assert payload["dataset_loaded"] is True


# ========================================================
# SESSIONS
# ========================================================


def test_create_then_list_a_session(client):
    created = client.post(
        "/sessions",
        headers=AUTH,
        json={"session_id": "alpha"},
    )

    assert created.status_code == 201

    listed = client.get(
        "/sessions", headers=AUTH
    ).json()

    ids = [
        session["session_id"]
        for session in listed
    ]

    assert "alpha" in ids


def test_get_unknown_session_is_404(client):
    response = client.get(
        "/sessions/ghost",
        headers=AUTH,
    )

    assert response.status_code == 404


def test_delete_unknown_session_is_404(client):
    response = client.delete(
        "/sessions/ghost",
        headers=AUTH,
    )

    assert response.status_code == 404


def test_delete_removes_a_populated_session(client):
    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "doomed",
            "message": "What was total revenue?",
        },
    )

    deleted = client.delete(
        "/sessions/doomed",
        headers=AUTH,
    )

    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    assert (
        client.get(
            "/sessions/doomed",
            headers=AUTH,
        ).status_code
        == 404
    )


def test_session_detail_returns_turns(client):
    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What was total revenue?",
        },
    )

    detail = client.get(
        "/sessions/s1",
        headers=AUTH,
    ).json()

    assert len(detail["turns"]) == 2
    assert detail["turns"][0]["role"] == "user"
    assert detail["turns"][1]["role"] == "assistant"


# ========================================================
# CHAT
# ========================================================


def test_chat_returns_the_analysis_contract(client):
    response = client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What was the total revenue?",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert set(payload["response"]) == {
        "answer",
        "analysis_type",
        "datasets_used",
        "calculations_performed",
        "key_findings",
        "sources",
        "confidence",
    }


def test_chat_creates_the_session_implicitly(client):
    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "brand_new",
            "message": "hello",
        },
    )

    assert (
        client.get(
            "/sessions/brand_new",
            headers=AUTH,
        ).status_code
        == 200
    )


def test_chat_persists_the_exchange(client):
    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What was total revenue?",
        },
    )

    detail = client.get(
        "/sessions/s1",
        headers=AUTH,
    ).json()

    assert detail["turns"][0]["content"] == (
        "What was total revenue?"
    )
    assert detail["turns"][1]["content"] == (
        "stub answer"
    )


def test_second_chat_uses_history(client, stub):
    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What was total revenue?",
        },
    )

    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What about the top product?",
        },
    )

    last = stub.structured_calls[-1]

    assert len(last) == 4


def test_sessions_do_not_share_history(client):
    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "alpha",
            "message": "alpha_secret",
        },
    )

    client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "beta",
            "message": "beta_question",
        },
    )

    alpha = client.get(
        "/sessions/alpha",
        headers=AUTH,
    ).json()

    assert (
        "beta_question"
        not in str(alpha["turns"])
    )


def test_empty_message_is_rejected(client):
    response = client.post(
        "/chat",
        headers=AUTH,
        json={"session_id": "s1", "message": ""},
    )

    assert response.status_code == 422


def test_missing_message_is_rejected(client):
    response = client.post(
        "/chat",
        headers=AUTH,
        json={"session_id": "s1"},
    )

    assert response.status_code == 422


def test_chat_reports_tools_and_visualisations(client):
    payload = client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What was total revenue?",
        },
    ).json()

    assert payload["tools_used"] == [
        "aggregate_dataset"
    ]
    assert payload["visualisations"] == []


def test_chat_records_the_dataset_used(client):
    payload = client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What was total revenue?",
        },
    ).json()

    assert payload["response"]["datasets_used"] == [
        DATASET_PATH
    ]


# ========================================================
# ANALYSE
# ========================================================


def test_analyse_without_session_is_stateless(client):
    response = client.post(
        "/analyse",
        headers=AUTH,
        json={"question": "What was total revenue?"},
    )

    assert response.status_code == 200

    sessions = client.get(
        "/sessions", headers=AUTH
    ).json()

    assert sessions == []


def test_analyse_with_session_persists(client):
    client.post(
        "/analyse",
        headers=AUTH,
        json={
            "question": "What was total revenue?",
            "session_id": "s1",
        },
    )

    assert client.get(
        "/sessions/s1",
        headers=AUTH,
    ).json()["turns"]


def test_analyse_returns_the_plan(client):
    payload = client.post(
        "/analyse",
        headers=AUTH,
        json={"question": "What was total revenue?"},
    ).json()

    assert payload["plan"]["dataset"] is True


def test_analyse_requires_a_question(client):
    response = client.post(
        "/analyse",
        headers=AUTH,
        json={},
    )

    assert response.status_code == 422


# ========================================================
# DATASETS
# ========================================================


def test_list_datasets_includes_the_loaded_one(client):
    payload = client.get(
        "/datasets", headers=AUTH
    ).json()

    names = [
        dataset["name"]
        for dataset in payload["datasets"]
    ]

    assert "sample_sales.xlsx" in names


def test_loaded_dataset_reports_shape(client):
    payload = client.get(
        "/datasets", headers=AUTH
    ).json()

    loaded = payload["datasets"][0]

    assert loaded["rows"] == 8
    assert "Revenue" in loaded["columns"]


def test_upload_a_dataset(client, tmp_path):
    source = tmp_path / "extra.csv"

    pd.DataFrame(
        {"Product": ["A"], "Revenue": [10]}
    ).to_csv(source, index=False)

    with source.open("rb") as handle:
        response = client.post(
            "/datasets",
            headers=AUTH,
            files={
                "file": ("extra.csv", handle, "text/csv")
            },
        )

    assert response.status_code == 201

    payload = response.json()

    assert payload["name"] == "extra.csv"
    assert payload["rows"] == 1


def test_uploaded_dataset_appears_in_the_list(
    client,
    tmp_path,
):
    source = tmp_path / "extra.csv"

    pd.DataFrame(
        {"Product": ["A"], "Revenue": [10]}
    ).to_csv(source, index=False)

    with source.open("rb") as handle:
        client.post(
            "/datasets",
            headers=AUTH,
            files={
                "file": ("extra.csv", handle, "text/csv")
            },
        )

    payload = client.get(
        "/datasets", headers=AUTH
    ).json()

    names = [
        dataset["name"]
        for dataset in payload["datasets"]
    ]

    assert "extra.csv" in names


# ========================================================
# DOCUMENTS
# ========================================================


def test_list_documents_starts_empty(client):
    payload = client.get(
        "/documents", headers=AUTH
    ).json()

    assert payload["documents"] == []


def test_upload_a_text_document(client, tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("Revenue fell in Q3.")

    with source.open("rb") as handle:
        response = client.post(
            "/documents",
            headers=AUTH,
            files={
                "file": ("notes.txt", handle, "text/plain")
            },
        )

    assert response.status_code == 201

    payload = response.json()

    assert payload["filename"] == "notes.txt"
    assert payload["size_bytes"] > 0


def test_uploaded_document_appears_in_the_list(
    client,
    tmp_path,
):
    source = tmp_path / "notes.txt"
    source.write_text("Revenue fell in Q3.")

    with source.open("rb") as handle:
        client.post(
            "/documents",
            headers=AUTH,
            files={
                "file": ("notes.txt", handle, "text/plain")
            },
        )

    payload = client.get(
        "/documents", headers=AUTH
    ).json()

    assert "notes.txt" in payload["documents"]


def test_unsupported_document_type_is_rejected(
    client,
    tmp_path,
):
    source = tmp_path / "malware.exe"
    source.write_bytes(b"MZ")

    with source.open("rb") as handle:
        response = client.post(
            "/documents",
            headers=AUTH,
            files={
                "file": (
                    "malware.exe",
                    handle,
                    "application/octet-stream",
                )
            },
        )

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_without_a_vector_store_still_succeeds(
    tmp_path,
):
    """
    An unbuilt index must degrade to "stored but not
    indexed", not fail the upload. Dataset and SQL
    analysis work without RAG.

    Exercised against the registry directly rather than
    through the app, because the app resolves the real
    vector store at startup and this path needs a store
    that genuinely is not there.
    """

    registry = DocumentRegistry(
        directory=tmp_path / "docs",
        vector_store=None,
    )

    source = tmp_path / "notes.txt"
    source.write_text("Revenue fell in Q3.")

    result = registry.store(
        source,
        "notes.txt",
        source.stat().st_size,
    )

    assert result["indexed"] is False
    assert result["chunks"] == 0
    assert "not indexed" in result["message"]
    assert Path(
        result["stored_path"]
    ).exists()


def test_document_is_indexed_when_a_store_exists(
    tmp_path,
):
    """
    The positive path: with a vector store available the
    document is actually chunked and added to it.
    """

    class FakeVectorStore:
        def __init__(self):
            self.added: list = []

        def add_documents(self, documents):
            self.added.extend(documents)

    store = FakeVectorStore()

    registry = DocumentRegistry(
        directory=tmp_path / "docs",
        vector_store=store,
    )

    source = tmp_path / "notes.txt"
    source.write_text(
        "Revenue fell in Q3. "
        "The channel expansion was delayed."
    )

    result = registry.store(
        source,
        "notes.txt",
        source.stat().st_size,
    )

    assert result["indexed"] is True
    assert result["chunks"] > 0
    assert store.added


# ========================================================
# REPORTS
# ========================================================


def test_unknown_report_is_404(client):
    response = client.get(
        "/reports/nope",
        headers=AUTH,
    )

    assert response.status_code == 404


def test_report_is_addressable_by_id():
    store = ReportStore()

    report_id = store.save("s1", "the report")

    assert store.get(report_id)["content"] == (
        "the report"
    )


def test_reports_are_listed_per_session():
    store = ReportStore()

    first = store.save("s1", "one")
    store.save("s2", "two")

    reports = store.list_for_session("s1")

    assert len(reports) == 1
    assert reports[0]["report_id"] == first


def test_unknown_report_returns_none():
    assert ReportStore().get("nope") is None


# ========================================================
# PATH SAFETY
# ========================================================


def test_traversal_filename_is_stripped():
    name = sanitise_filename(
        "../../etc/passwd"
    )

    assert "/" not in name
    assert ".." not in name


def test_windows_traversal_filename_is_stripped():
    name = sanitise_filename(
        r"..\..\windows\system32\evil.exe"
    )

    assert "\\" not in name
    assert "/" not in name


def test_filename_with_no_usable_characters_rejected():
    with pytest.raises(ValueError):
        sanitise_filename("...")


def test_upload_traversal_stays_in_the_directory(
    client,
    tmp_path,
):
    source = tmp_path / "payload.csv"
    source.write_text("Product,Revenue\nA,10\n")

    with source.open("rb") as handle:
        client.post(
            "/datasets",
            headers=AUTH,
            files={
                "file": (
                    "../../evil.csv",
                    handle,
                    "text/csv",
                )
            },
        )

    stored = (
        client.get("/datasets", headers=AUTH)
        .json()["datasets"]
    )

    for dataset in stored:
        assert ".." not in dataset["path"]


# ========================================================
# LIMITS
# ========================================================


def test_document_size_limit_exists():
    assert MAX_DOCUMENT_BYTES > 0


def test_oversized_document_is_rejected(tmp_path):
    registry = DocumentRegistry(
        directory=tmp_path / "docs"
    )

    source = tmp_path / "big.txt"
    source.write_text("x" * 10)

    with pytest.raises(ValueError):
        registry.store(
            source,
            "big.txt",
            MAX_DOCUMENT_BYTES + 1,
        )
