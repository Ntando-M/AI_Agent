"""FastAPI service over the shared analysis engine.

This layer adds transport and nothing else. Every question
is answered by the same Orchestrator the CLI uses, and
every conversation is stored by the same ConversationStore.
That shared core is the point of V9: adding a client must
not add a second implementation.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import tempfile
import time
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

from api.logging_config import (
    configure_logging,
    get_logger,
    log_event,
    set_request_id,
)
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
    DeleteUploadResponse,
    DocumentListResponse,
    ErrorResponse,
    GenerateReportRequest,
    HealthResponse,
    ReportPayload,
    ReportSummaryPayload,
    SessionDetail,
    SessionPayload,
    TurnPayload,
    UploadResponse,
)
from api.settings import Settings, require_api_key
from llm.groq_provider import RateLimitError
from api.timeouts import (
    OperationTimeout,
    clear_request_state,
    run_with_timeout,
)
from api.uploads import (
    UploadPolicy,
    UploadRejected,
    sanitise_filename,
)
from memory.sqlite_store import SQLiteConversationStore
from data_analysis import load_dataset
from data_analysis.reporting import (
    build_report_document,
)
from data_analysis.tool_models import PlanNotProducedError
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


def _chart_data_url(
    path: str,
    chart_directory: str,
) -> str | None:
    """
    Read a chart PNG and return it as a data URL.

    The path is constrained to the configured chart
    directory before anything is read. A stored report is
    data on disk and could have been edited, so treating
    its paths as trusted would turn the reports endpoint
    into an arbitrary-file-read primitive.

    Returns None when the file is missing, so one absent
    chart degrades to "not shown" rather than failing the
    whole report.
    """

    try:
        root = Path(chart_directory).resolve()
        candidate = Path(path).resolve()
    except (OSError, ValueError):
        return None

    if not candidate.is_file():
        return None

    if root != candidate and root not in candidate.parents:
        return None

    try:
        encoded = base64.b64encode(
            candidate.read_bytes()
        ).decode("ascii")
    except OSError:
        return None

    return f"data:image/png;base64,{encoded}"


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

    configure_logging()

    logger = get_logger("api")
    request_logger = get_logger("api.request")

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

    reports = ReportStore(
        directory=settings.reports_directory,
    )

    dataset_policy = UploadPolicy.for_datasets(
        settings.max_dataset_upload_bytes
    )

    document_policy = UploadPolicy.for_documents(
        settings.max_document_upload_bytes
    )

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
            "X-Request-ID",
        ],
    )

    # ====================================================
    # REQUEST OBSERVABILITY
    # ====================================================

    @app.middleware("http")
    async def observe_request(request, call_next):
        """
        Bind a correlation id, time the request, and log both
        outcomes.

        A client-supplied X-Request-ID is honoured so a trace
        started at an upstream service can be followed here. The
        id is sanitised in set_request_id because it is
        attacker-controlled and is written verbatim to the log.

        Failures are logged with the exception attached and
        then re-raised: swallowing them would turn a bug into a
        silent 200. The id is always cleared, including on the
        error path, so a leaked value cannot be inherited by the
        next request on a reused worker.
        """

        request_id = set_request_id(
            request.headers.get("X-Request-ID")
        )

        started = time.monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int(
                (time.monotonic() - started)
                * 1000
            )

            log_event(
                request_logger,
                logging.ERROR,
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
                error_type=type(exc).__name__,
            )

            clear_request_state()
            raise

        duration_ms = int(
            (time.monotonic() - started) * 1000
        )

        log_event(
            request_logger,
            logging.INFO,
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id

        clear_request_state()

        return response

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
            request.session_id,
            name=request.name,
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
        response: dict,
        visualisations: list[str] | None = None,
        tools_used: list[str] | None = None,
        source_labels: list[str] | None = None,
    ) -> None:
        """
        Record the exchange and the answer's evidence.

        The evidence is what makes a restored turn show its
        confidence and sources instead of the answer text
        alone. It is stored alongside the message rather
        than rebuilt from it, because the answer string does
        not contain the analysis type, the confidence score
        or the source list in any recoverable form.
        """

        store.add_turn(
            session_id,
            question,
            response["answer"],
            evidence={
                "analysis_type": response.get(
                    "analysis_type", ""
                ),
                "confidence": response.get(
                    "confidence", 0.0
                ),
                "sources": list(
                    response.get("sources", [])
                ),
                "datasets_used": list(
                    response.get("datasets_used", [])
                ),
                "calculations_performed": list(
                    response.get(
                        "calculations_performed", []
                    )
                ),
                "key_findings": list(
                    response.get("key_findings", [])
                ),
                "visualisations": list(
                    visualisations or []
                ),
                "tools_used": list(tools_used or []),
                "source_labels": list(
                    source_labels or []
                ),
            },
        )

    def _report_payload(
        report: dict,
    ) -> ReportPayload:
        """
        One stored report, with its charts encoded.

        Encoding happens here rather than at save time so
        the persisted file stays small and a report can
        later be served as real image URLs without
        migrating stored data.
        """

        charts = report.get("charts") or {}

        images = {}

        for name, path in charts.items():
            data_url = _chart_data_url(
                path,
                settings.chart_directory,
            )

            if data_url is not None:
                images[name] = data_url

        return ReportPayload(
            **{
                **report,
                "chart_images": images,
            }
        )

    def _analysis_payload(
        response: dict,
    ) -> AnalysisPayload:
        return AnalysisPayload(
            **response
        )

    def _run_analysis(
        question: str,
        history: list,
        endpoint: str,
    ) -> dict:
        """
        Run the orchestrator under a wall-clock bound.

        The orchestrator reaches a cloud or local LLM, the
        dataset, SQLite and matplotlib. Any of those can block
        indefinitely, so the whole call is bounded and the
        duration logged. A timeout is reported as 504 rather
        than 500 so a caller can tell "too slow" from "broken".

        The question is logged and the answer is not: the
        question explains what was asked, the answer may carry
        figures derived from the dataset.
        """

        try:
            outcome, report = run_with_timeout(
                orchestrator.handle,
                question,
                history=history,
                timeout_seconds=(
                    settings.analysis_timeout_seconds
                ),
                label=f"{endpoint}.orchestrator",
            )
        except OperationTimeout as exc:
            log_event(
                request_logger,
                logging.ERROR,
                "analysis_timeout",
                endpoint=endpoint,
                timeout_seconds=(
                    settings.analysis_timeout_seconds
                ),
                question_length=len(question),
            )

            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=str(exc),
            ) from exc
        except RateLimitError as exc:
            # A quota refusal is not a bug and not a provider
            # failure. Reporting it as 500 sends whoever is
            # debugging looking at the wrong layer. 429 with
            # Groq's own wording tells the user what actually
            # happened and when to try again.
            log_event(
                request_logger,
                logging.WARNING,
                "analysis_rate_limited",
                endpoint=endpoint,
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_429_TOO_MANY_REQUESTS
                ),
                detail=(
                    "The model's token quota is exhausted. "
                    f"{exc.detail}"
                ),
            ) from exc
        except Exception as exc:
            log_event(
                request_logger,
                logging.ERROR,
                "analysis_failed",
                endpoint=endpoint,
                error_type=type(exc).__name__,
                error=str(exc),
            )

            # A planner that returned no usable plan is a
            # request the engine could not act on, not a
            # server fault. Reporting it as 422 keeps a 5xx
            # meaning "something broke" instead of "the model
            # answered the wrong shape", which is what sent
            # whoever was debugging looking at the wrong
            # layer.
            if isinstance(exc, PlanNotProducedError):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=str(exc),
                ) from exc

            # The model answered, but not in the shape the
            # contract requires. That is a provider problem,
            # not the caller's, so it stays a 5xx - but it is
            # reported as a bad gateway rather than a bare
            # JSON decode error, which named neither the
            # cause nor the layer.
            if isinstance(exc, json.JSONDecodeError):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "The model returned a response that "
                        "could not be parsed as JSON."
                    ),
                ) from exc

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=f"Analysis failed: {exc}",
            ) from exc

        log_event(
            request_logger,
            logging.INFO,
            "analysis_completed",
            endpoint=endpoint,
            duration_ms=report.duration_ms,
            tools_used=outcome["tools_used"],
            tools_count=len(outcome["tools_used"]),
            visualisations_count=len(
                outcome["visualisations"]
            ),
            analysis_type=outcome["response"][
                "analysis_type"
            ],
            confidence=outcome["response"]["confidence"],
            sources_count=len(
                outcome["source_labels"]
            ),
        )

        return outcome

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

        outcome = _run_analysis(
            request.message,
            history,
            endpoint="chat",
        )

        response = outcome["response"]

        _persist(
            request.session_id,
            request.message,
            response,
            visualisations=outcome["visualisations"],
            tools_used=outcome["tools_used"],
            source_labels=outcome["source_labels"],
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

        outcome = _run_analysis(
            request.question,
            history,
            endpoint="analyse",
        )

        if request.session_id:
            _persist(
                request.session_id,
                request.question,
                outcome["response"],
                visualisations=outcome["visualisations"],
                tools_used=outcome["tools_used"],
                source_labels=outcome.get(
                    "source_labels", []
                ),
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
        """
        Accept a dataset under a size and type limit.

        The client filename is sanitised to a bare basename and
        its extension checked before a single byte is written.
        The body is then copied in chunks and abandoned at the
        limit, so an oversized upload never lands whole on disk.

        A rejected upload is 413 when it is too large and 400
        when the type is wrong, so a client can tell a size
        problem from a format problem.
        """

        safe_name = sanitise_filename(
            file.filename, "upload.csv"
        )

        try:
            dataset_policy.validate_extension(
                safe_name
            )
        except UploadRejected as exc:
            log_event(
                request_logger,
                logging.WARNING,
                "upload_rejected",
                kind="dataset",
                reason=str(exc),
                extension=Path(safe_name).suffix.lower(),
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        with tempfile.TemporaryDirectory() as staging:
            staged = Path(staging) / safe_name

            try:
                written = dataset_policy.copy_stream_to(
                    file.file,
                    staged,
                    filename=safe_name,
                )
            except UploadRejected as exc:
                log_event(
                    request_logger,
                    logging.WARNING,
                    "upload_rejected",
                    kind="dataset",
                    reason=str(exc),
                    limit_bytes=(
                        dataset_policy.max_bytes
                    ),
                )

                raise HTTPException(
                    status_code=(
                        status.HTTP_413_CONTENT_TOO_LARGE
                    ),
                    detail=str(exc),
                ) from exc

            log_event(
                request_logger,
                logging.INFO,
                "upload_accepted",
                kind="dataset",
                filename=safe_name,
                bytes_written=written,
            )

            try:
                return DatasetPayload(
                    **datasets.register_from_upload(
                        staged,
                        safe_name,
                    )
                )
            except Exception as exc:
                log_event(
                    request_logger,
                    logging.WARNING,
                    "dataset_registration_failed",
                    filename=safe_name,
                    error=str(exc),
                )

                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=(
                        "Could not register the "
                        f"dataset: {exc}"
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
        """
        Accept a document under a size and type limit.

        Same two-stage guard as a dataset upload: sanitise and
        check the extension first, then stream with a running
        byte count. Only the formats the RAG loader can actually
        read are accepted, so a file that passes the limit is
        still a file the pipeline can process.
        """

        safe_name = sanitise_filename(
            file.filename, "upload.txt"
        )

        try:
            document_policy.validate_extension(
                safe_name
            )
        except UploadRejected as exc:
            log_event(
                request_logger,
                logging.WARNING,
                "upload_rejected",
                kind="document",
                reason=str(exc),
                extension=Path(safe_name).suffix.lower(),
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        with tempfile.TemporaryDirectory() as staging:
            staged = Path(staging) / safe_name

            try:
                written = document_policy.copy_stream_to(
                    file.file,
                    staged,
                    filename=safe_name,
                )
            except UploadRejected as exc:
                log_event(
                    request_logger,
                    logging.WARNING,
                    "upload_rejected",
                    kind="document",
                    reason=str(exc),
                    limit_bytes=(
                        document_policy.max_bytes
                    ),
                )

                raise HTTPException(
                    status_code=(
                        status.HTTP_413_CONTENT_TOO_LARGE
                    ),
                    detail=str(exc),
                ) from exc

            log_event(
                request_logger,
                logging.INFO,
                "upload_accepted",
                kind="document",
                filename=safe_name,
                bytes_written=written,
            )

            try:
                return UploadResponse(
                    **documents.store(
                        staged,
                        safe_name,
                        written,
                    )
                )
            except Exception as exc:
                log_event(
                    request_logger,
                    logging.WARNING,
                    "document_store_failed",
                    filename=safe_name,
                    error=str(exc),
                )

                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=str(exc),
                ) from exc

    @app.delete(
        "/documents/{name}",
        response_model=DeleteUploadResponse,
        dependencies=[auth],
    )
    def delete_document(
        name: str,
    ) -> DeleteUploadResponse:
        """
        Delete a document and its indexed chunks.

        The file and its embeddings go together: leaving the
        chunks behind would let the engine keep citing a
        document that no longer exists.
        """

        # Counted inside the registry, so one sanitisation of
        # the name resolves both the file and its chunks.
        try:
            deleted, chunks_removed = documents.delete(name)
        except Exception as exc:
            log_event(
                request_logger,
                logging.ERROR,
                "document_index_removal_failed",
                filename=name,
                error=str(exc),
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    "The document was not deleted because its "
                    f"indexed chunks could not be removed: {exc}"
                ),
            ) from exc

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{name}' not found.",
            )

        log_event(
            request_logger,
            logging.INFO,
            "document_deleted",
            filename=name,
            chunks_removed=chunks_removed,
        )

        return DeleteUploadResponse(
            name=name,
            deleted=True,
            chunks_removed=chunks_removed,
        )

    @app.delete(
        "/datasets/{name}",
        response_model=DeleteUploadResponse,
        dependencies=[auth],
    )
    def delete_dataset(
        name: str,
    ) -> DeleteUploadResponse:
        """
        Delete an uploaded dataset.

        Only files in the upload directory can be removed.
        The configured analysis dataset lives outside it, so a
        request naming it cannot delete the file the engine is
        currently analysing.
        """

        deleted = datasets.delete(name)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Dataset '{name}' not found in the "
                    f"upload directory."
                ),
            )

        log_event(
            request_logger,
            logging.INFO,
            "dataset_deleted",
            filename=name,
        )

        return DeleteUploadResponse(
            name=name,
            deleted=True,
        )

    # ====================================================
    # REPORTS
    # ====================================================

    @app.post(
        "/reports",
        response_model=ReportPayload,
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth],
    )
    def generate_report(
        request: GenerateReportRequest,
    ) -> ReportPayload:
        """
        Generate a deterministic report for a dataset and
        persist it.

        The source is the dataset named in the request, or
        the one the engine has loaded when none is named. The
        named source is resolved through the registry, which
        sanitises the name and confines it to the upload
        directory - a client-supplied string is never used as
        a path directly.

        No LLM is involved: the report is arithmetic over
        the dataframe, so it is reproducible and cannot
        invent a finding. The model's role elsewhere is to
        choose operations, not to author reports.
        """

        dataframe = None
        dataset_name = None

        if request.dataset:
            resolved = datasets.get(request.dataset)

            if resolved is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_404_NOT_FOUND
                    ),
                    detail=(
                        f"Dataset '{request.dataset}' "
                        f"not found."
                    ),
                )

            try:
                dataframe = load_dataset(str(resolved))
            except Exception as exc:
                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=(
                        f"Could not read dataset "
                        f"'{request.dataset}': {exc}"
                    ),
                ) from exc

            dataset_name = resolved.name

        elif orchestrator.data_agent is not None:
            dataframe = (
                orchestrator.data_agent.dataframe
            )

            dataset_name = (
                Path(orchestrator.dataset_path).name
                if orchestrator.dataset_path
                else None
            )

        if dataframe is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "No dataset is loaded and none was "
                    "named, so a report cannot be "
                    "generated."
                ),
            )

        try:
            document = build_report_document(
                dataframe,
                dataset_name=dataset_name,
                report_directory=(
                    settings.reports_directory
                ),
                chart_directory=(
                    settings.chart_directory
                ),
            )
        except Exception as exc:
            log_event(
                request_logger,
                logging.ERROR,
                "report_generation_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=f"Report generation failed: {exc}",
            ) from exc

        report_id = reports.save(
            request.session_id,
            document["content"],
            dataset_name=document["dataset_name"],
            summary=document["summary"],
            layers=document["layers"],
            charts=document["charts"],
        )

        log_event(
            request_logger,
            logging.INFO,
            "report_generated",
            report_id=report_id,
            rows=document["summary"].get("rows"),
        )

        stored = reports.get(report_id)

        if stored is None:
            # Written a moment ago and already unreadable:
            # the store is not working, which is a server
            # fault rather than a bad request.
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    "The report was generated but could "
                    "not be read back."
                ),
            )

        return _report_payload(stored)

    @app.get(
        "/reports",
        response_model=list[ReportSummaryPayload],
        dependencies=[auth],
    )
    def list_reports() -> list[ReportSummaryPayload]:
        """
        Every stored report, newest first.

        A summary rather than the full payload: the list
        view needs a label and a date, and encoding every
        chart of every report to render a list would be
        wasteful.
        """

        return [
            ReportSummaryPayload(
                report_id=report["report_id"],
                session_id=report.get("session_id"),
                dataset_name=report.get(
                    "dataset_name"
                ),
                created_at=report.get("created_at"),
                preview=(
                    report.get("content") or ""
                )[:120],
            )
            for report in reports.list_reports()
        ]

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

        return _report_payload(report)

    @app.delete(
        "/reports/{report_id}",
        response_model=DeleteUploadResponse,
        dependencies=[auth],
    )
    def delete_report(
        report_id: str,
    ) -> DeleteUploadResponse:
        """
        Remove one stored report.

        404 for an unknown id rather than a silent 200, so a
        client can tell "already gone" from "just removed".
        The response reuses the upload-delete shape because
        both report a name and whether anything was removed.
        """

        if not reports.delete(report_id):
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    f"Report '{report_id}' not found."
                ),
            )

        log_event(
            request_logger,
            logging.INFO,
            "report_deleted",
            report_id=report_id,
        )

        return DeleteUploadResponse(
            name=report_id,
            deleted=True,
            chunks_removed=0,
        )

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