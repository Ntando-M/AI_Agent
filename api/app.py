"""FastAPI service over the shared analysis engine.

This layer adds transport and nothing else. Every question
is answered by the same Orchestrator the CLI uses, and
every conversation is stored by the same ConversationStore.
That shared core is the point of V9: adding a client must
not add a second implementation.
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware

from api.registry import (
    DatasetRegistry,
    DocumentRegistry,
    ReportStore,
)
from api.schemas import (
    AnalyseRequest,
    AnalyseResponse,
    AnalysisPayload,
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    DatasetListResponse,
    DatasetPayload,
    DeleteResponse,
    DocumentListResponse,
    HealthResponse,
    ReportPayload,
    SessionDetail,
    SessionPayload,
    TurnPayload,
    UploadResponse,
)
from api.settings import Settings, require_api_key
from memory.sqlite_store import SQLiteConversationStore
from orchestrator.llm_gateway import LLMGateway
from orchestrator.orchestrator import Orchestrator


load_dotenv()


def build_orchestrator(
    settings: Settings,
) -> Orchestrator:
    """
    Construct the single engine the API uses.

    The provider comes from configuration, resolved once at
    startup, so every request is served by the same model
    and swapping providers is a restart rather than a
    request parameter.
    """

    gateway = LLMGateway.build(settings.provider)

    database_path = None

    if settings.analytics_database_exists():
        database_path = (
            settings.analytics_database_path
        )

    return Orchestrator(
        gateway=gateway,
        dataset_path=settings.dataset_path,
        database_path=database_path,
    )


def load_vector_store_or_none(
    settings: Settings,
) -> Any | None:
    """
    Load the Chroma store, or return None.

    An absent or unbuilt index must not stop the service:
    dataset and SQL analysis work without RAG, so document
    endpoints report that indexing is unavailable rather
    than the whole API being down.
    """

    try:
        from rag.vector_store import (
            load_vector_store,
        )

        return load_vector_store()
    except Exception:
        return None


def create_app(
    settings: Settings | None = None,
    orchestrator: Orchestrator | None = None,
) -> FastAPI:
    """
    Build the application.

    Both the settings and the orchestrator are injectable
    so tests can supply a stub gateway and a temporary
    database. Production passes neither and gets the real
    engine from configuration.
    """

    settings = settings or Settings.from_env()
    require_api_key(settings)

    if orchestrator is None:
        orchestrator = build_orchestrator(
            settings
        )

    store = SQLiteConversationStore(
        database_url=settings.chat_database_url
    )

    datasets = DatasetRegistry(
        upload_directory=(
            settings.dataset_upload_directory
        )
    )

    documents = DocumentRegistry(
        directory=settings.documents_directory,
        vector_store=load_vector_store_or_none(
            settings
        ),
    )

    reports = ReportStore()

    app = FastAPI(
        title="AI Data Analyst API",
        version=settings.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(
            settings.allowed_origins
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=[
            settings.api_key_header,
            "Content-Type",
        ],
    )

    # ====================================================
    # AUTH
    # ====================================================

    def verify_api_key(
        x_api_key: str | None = Header(
            default=None,
            alias="X-API-Key",
        ),
    ) -> None:
        """
        Reject a request without a valid key.

        Compared with secrets.compare_digest so a wrong key
        cannot be recovered by timing the response. The
        header name comes from settings, so the alias is
        fixed at import but the expected value is not.
        """

        if not x_api_key:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Missing API key. Send the "
                    f"{settings.api_key_header} header."
                ),
            )

        if not secrets.compare_digest(
            x_api_key,
            settings.api_key or "",
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail="Invalid API key.",
            )

    auth = Depends(verify_api_key)

    # ====================================================
    # HEALTH
    # ====================================================

    @app.get(
        "/health",
        response_model=HealthResponse,
    )
    def health() -> HealthResponse:
        """
        Liveness and readiness.

        Deliberately unauthenticated: a probe needs to
        report that the service is up, and it exposes no
        data, only booleans.
        """

        return HealthResponse(
            status="ok",
            provider=settings.provider,
            dataset_loaded=(
                orchestrator.has_dataset
            ),
            database_loaded=(
                orchestrator.has_database
            ),
            documents_indexed=(
                documents.vector_store is not None
            ),
            version=settings.version,
        )

    # ====================================================
    # SESSIONS
    # ====================================================

    @app.get(
        "/sessions",
        response_model=list[SessionPayload],
        dependencies=[auth],
    )
    def list_sessions() -> list[SessionPayload]:
        return [
            SessionPayload(**summary.as_dict())
            for summary in store.list_sessions()
        ]

    @app.post(
        "/sessions",
        response_model=SessionPayload,
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth],
    )
    def create_session(
        request: CreateSessionRequest,
    ) -> SessionPayload:
        summary = store.create_session(
            request.session_id
        )

        return SessionPayload(**summary.as_dict())

    @app.get(
        "/sessions/{session_id}",
        response_model=SessionDetail,
        dependencies=[auth],
    )
    def get_session(
        session_id: str,
    ) -> SessionDetail:
        if not store.session_exists(session_id):
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    f"Session '{session_id}' not found."
                ),
            )

        return SessionDetail(
            session_id=session_id,
            turns=[
                TurnPayload(**turn.as_dict())
                for turn in store.get_turns(session_id)
            ],
        )

    @app.delete(
        "/sessions/{session_id}",
        response_model=DeleteResponse,
        dependencies=[auth],
    )
    def delete_session(
        session_id: str,
    ) -> DeleteResponse:
        deleted = store.delete_session(session_id)

        if not deleted:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    f"Session '{session_id}' not found."
                ),
            )

        return DeleteResponse(
            session_id=session_id,
            deleted=True,
        )

    # ====================================================
    # CHAT AND ANALYSIS
    # ====================================================

    def _persist(
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        store.add_turn(
            session_id,
            question,
            answer,
        )

    def _analysis_payload(
        response: dict,
    ) -> AnalysisPayload:
        return AnalysisPayload(
            **response
        )

    @app.post(
        "/chat",
        response_model=ChatResponse,
        dependencies=[auth],
    )
    def chat(
        request: ChatRequest,
    ) -> ChatResponse:
        """
        Ask a question inside a conversation.

        The session is created on first use, so a client
        can start chatting without a separate setup call.
        """

        store.create_session(request.session_id)

        history = store.get_messages(
            request.session_id
        )

        try:
            outcome = orchestrator.handle(
                request.message,
                history=history,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=f"Analysis failed: {exc}",
            ) from exc

        response = outcome["response"]

        _persist(
            request.session_id,
            request.message,
            response["answer"],
        )

        return ChatResponse(
            session_id=request.session_id,
            response=_analysis_payload(response),
            visualisations=outcome["visualisations"],
            tools_used=outcome["tools_used"],
            source_labels=outcome["source_labels"],
            warnings=list(
                orchestrator.load_warnings
            ),
        )

    @app.post(
        "/analyse",
        response_model=AnalyseResponse,
        dependencies=[auth],
    )
    def analyse(
        request: AnalyseRequest,
    ) -> AnalyseResponse:
        """
        Ask a question without necessarily persisting it.

        Supplying session_id reads that conversation for
        context; omitting it makes the question stateless.
        """

        history = []

        if request.session_id:
            history = store.get_messages(
                request.session_id
            )

        try:
            outcome = orchestrator.handle(
                request.question,
                history=history,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=f"Analysis failed: {exc}",
            ) from exc

        if request.session_id:
            _persist(
                request.session_id,
                request.question,
                outcome["response"]["answer"],
            )

        return AnalyseResponse(
            response=_analysis_payload(
                outcome["response"]
            ),
            visualisations=outcome["visualisations"],
            tools_used=outcome["tools_used"],
            plan=outcome["plan"],
            warnings=list(
                orchestrator.load_warnings
            ),
        )

    # ====================================================
    # DATASETS
    # ====================================================

    @app.get(
        "/datasets",
        response_model=DatasetListResponse,
        dependencies=[auth],
    )
    def list_datasets() -> DatasetListResponse:
        payloads = [
            DatasetPayload(**entry)
            for entry in datasets.list_datasets()
        ]

        if orchestrator.dataset_path is not None:
            payloads.insert(
                0,
                DatasetPayload(
                    name=Path(
                        orchestrator.dataset_path
                    ).name,
                    path=str(
                        orchestrator.dataset_path
                    ),
                    rows=(
                        len(
                            orchestrator.data_agent
                            .dataframe
                        )
                        if orchestrator.data_agent
                        else None
                    ),
                    columns=(
                        list(
                            orchestrator.data_agent
                            .dataframe.columns
                        )
                        if orchestrator.data_agent
                        else []
                    ),
                    registered=True,
                ),
            )

        return DatasetListResponse(
            datasets=payloads
        )

    @app.post(
        "/datasets",
        response_model=DatasetPayload,
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth],
    )
    def upload_dataset(
        file: UploadFile = File(...),
    ) -> DatasetPayload:
        with tempfile.TemporaryDirectory() as staging:
            staged = (
                Path(staging)
                / (file.filename or "upload.csv")
            )

            with staged.open("wb") as handle:
                shutil.copyfileobj(
                    file.file,
                    handle,
                )

            try:
                return DatasetPayload(
                    **datasets.register_from_upload(
                        staged,
                        file.filename or "upload.csv",
                    )
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=(
                        f"Could not register the dataset: "
                        f"{exc}"
                    ),
                ) from exc

    # ====================================================
    # DOCUMENTS
    # ====================================================

    @app.get(
        "/documents",
        response_model=DocumentListResponse,
        dependencies=[auth],
    )
    def list_documents() -> DocumentListResponse:
        return DocumentListResponse(
            documents=documents.list_documents()
        )

    @app.post(
        "/documents",
        response_model=UploadResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth],
    )
    def upload_document(
        file: UploadFile = File(...),
    ) -> UploadResponse:
        with tempfile.TemporaryDirectory() as staging:
            staged = (
                Path(staging)
                / (file.filename or "upload.txt")
            )

            with staged.open("wb") as handle:
                shutil.copyfileobj(
                    file.file,
                    handle,
                )

            try:
                return UploadResponse(
                    **documents.store(
                        staged,
                        file.filename or "upload.txt",
                        staged.stat().st_size,
                    )
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=str(exc),
                ) from exc

    # ====================================================
    # REPORTS
    # ====================================================

    @app.get(
        "/reports/{report_id}",
        response_model=ReportPayload,
        dependencies=[auth],
    )
    def get_report(
        report_id: str,
    ) -> ReportPayload:
        report = reports.get(report_id)

        if report is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    f"Report '{report_id}' not found."
                ),
            )

        return ReportPayload(**report)

    return app


app = None


def get_app() -> FastAPI:
    """
    Lazily build the module-level app.

    Built on first call rather than at import so that a
    missing API_KEY produces a clear startup error instead
    of breaking collection for every test that imports the
    module.
    """

    global app

    if app is None:
        app = create_app()

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.app:get_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
    )