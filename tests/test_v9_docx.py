from __future__ import annotations

import pytest

from docx import Document as DocxDocument

from rag.document_loader import (
    load_documents,
    load_docx_file,
)


def build_docx(
    path,
    paragraphs: list[str],
) -> None:
    """
    Write a minimal DOCX so the loader is tested against a file
    this test controls, not a committed document that may be
    regenerated or deleted.
    """

    document = DocxDocument()

    for text in paragraphs:
        document.add_paragraph(text)

    document.save(str(path))


def test_docx_paragraphs_become_documents(tmp_path):
    path = tmp_path / "sample.docx"

    build_docx(
        path,
        [
            "First paragraph.",
            "Second paragraph.",
        ],
    )

    documents = load_docx_file(str(path))

    assert len(documents) == 2

    assert (
        documents[0].page_content
        == "First paragraph."
    )

    assert (
        documents[1].page_content
        == "Second paragraph."
    )


def test_docx_metadata_matches_pdf_shape(tmp_path):
    """
    The PDF loader records source, filename and page. DOCX has
    no pages, but callers chunk on this metadata, so the keys
    must be identical or a downstream consumer has to branch on
    file format.
    """

    path = tmp_path / "shaped.docx"
    build_docx(path, ["Only paragraph."])

    document = load_docx_file(str(path))[0]

    assert document.metadata["filename"] == "shaped.docx"
    assert document.metadata["source"] == str(path)
    assert document.metadata["page"] == 1


def test_empty_paragraphs_are_dropped(tmp_path):
    """
    Empty paragraphs would otherwise become empty chunks that
    embed to noise and dilute retrieval.
    """

    path = tmp_path / "sparse.docx"

    build_docx(
        path,
        [
            "Kept.",
            "",
            "   ",
            "Also kept.",
        ],
    )

    documents = load_docx_file(str(path))

    assert len(documents) == 2


def test_docx_rejects_wrong_extension(tmp_path):
    path = tmp_path / "not_a_docx.txt"
    path.write_text("plain text", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Expected a DOCX file",
    ):
        load_docx_file(str(path))


def test_docx_missing_file_raises(tmp_path):
    with pytest.raises(
        FileNotFoundError,
        match="File not found",
    ):
        load_docx_file(
            str(tmp_path / "absent.docx")
        )


def test_load_documents_picks_up_docx(tmp_path):
    """
    The directory loader must discover DOCX without a caller
    having to know which formats are present.
    """

    build_docx(
        tmp_path / "one.docx", ["Docx content."]
    )
    (tmp_path / "two.txt").write_text(
        "Text content.", encoding="utf-8"
    )

    documents = load_documents(str(tmp_path))

    filenames = {
        document.metadata["filename"]
        for document in documents
    }

    assert filenames == {"one.docx", "two.txt"}


def test_indexing_a_docx_reaches_the_vector_store(tmp_path):
    """
    The regression test for the real defect.

    load_docx_file was correct and tested, but nothing called
    it: DocumentRegistry.index dispatched only .pdf and .txt,
    so every uploaded DOCX was stored, reported as stored, and
    silently never indexed. Testing the loader in isolation
    proved nothing about retrieval, which is what the feature
    exists for.
    """

    from api.registry import DocumentRegistry

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

    source = tmp_path / "strategy.docx"
    build_docx(source, ["Revenue grew 12%.", "Costs fell 4%."])

    result = registry.store(
        source,
        "strategy.docx",
        source.stat().st_size,
    )

    assert result["indexed"] is True
    assert result["chunks"] == 2
    assert store.added

    contents = {doc.page_content for doc in store.added}

    assert contents == {"Revenue grew 12%.", "Costs fell 4%."}


def test_load_documents_scans_subdirectories(tmp_path):
    """
    The corpus is organised into per-format subdirectories
    (documents/pdf, documents/word), so a non-recursive glob
    finds nothing at the top level and the directory loader
    returns an empty corpus while every file is present.
    """

    nested = tmp_path / "word"
    nested.mkdir()

    build_docx(nested / "nested.docx", ["Nested content."])

    deep = tmp_path / "pdf"
    deep.mkdir()

    (deep / "deep.txt").write_text(
        "Deep text content.", encoding="utf-8"
    )

    documents = load_documents(str(tmp_path))

    filenames = {
        document.metadata["filename"]
        for document in documents
    }

    assert filenames == {"nested.docx", "deep.txt"}


def test_committed_strategy_document_loads():
    """
    The generated strategy document is part of the RAG corpus,
    so it must survive a real load. This is the regression test
    for the DOCX path end to end.
    """

    documents = load_docx_file(
        "documents/word/FY2026_Sales_Strategy.docx"
    )

    assert documents

    combined = "\n".join(
        document.page_content
        for document in documents
    )

    assert "FY2026 Sales Performance" in combined

    # The document is generated from the sales database, so a
    # figure from that database must appear in it. If the data
    # changes without a regeneration, this fails loudly rather
    # than letting the corpus serve a stale strategy.
    assert "R274,000" in combined