import os
import time
from datetime import datetime
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

ALLOWED_TYPES = ["pdf", "docx", "txt", "csv", "xlsx"]
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
NOT_FOUND_ANSWER = "I could not find an answer in your uploaded documents."
PENDING_DOCUMENT_STATUSES = {"uploaded", "processing"}

STATUS_LABELS = {
    "uploaded": "Queued",
    "processing": "Processing",
    "processed": "Ready",
    "failed": "Failed",
}

STAGE_LABELS = {
    "queued": "Waiting in queue",
    "starting": "Starting processing",
    "file download": "Downloading file",
    "text extraction": "Extracting text",
    "content storage": "Saving document content",
    "text chunking": "Creating searchable chunks",
    "chunk storage": "Saving chunks",
    "embedding generation": "Generating embeddings",
    "vector indexing": "Indexing for search",
    "completed": "Processing complete",
}


@st.cache_resource
def get_supabase_client() -> Client:
    """Create and cache the Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_auth_headers() -> dict[str, str]:
    """Build FastAPI authorization headers from the active Supabase session."""
    session = st.session_state.get("session")

    if not session:
        return {}

    return {"Authorization": f"Bearer {session.access_token}"}


def get_api_error_message(
    response: requests.Response,
    fallback_message: str,
) -> str:
    """Extract a safe error message from a FastAPI response."""
    try:
        response_data = response.json()
    except ValueError:
        return fallback_message

    detail = response_data.get("detail")

    if isinstance(detail, str) and detail.strip():
        return detail

    return fallback_message


def format_file_size(file_size_bytes: int | None) -> str:
    """Render bytes in a compact human-readable form."""
    if not file_size_bytes:
        return "Unknown size"

    units = ["B", "KB", "MB", "GB"]
    size = float(file_size_bytes)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{file_size_bytes} B"


def format_created_at(value: str | None) -> str:
    """Render an ISO timestamp without making timezone claims."""
    if not value:
        return "Unknown date"

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%d %b %Y, %I:%M %p"
        )
    except ValueError:
        return value


def get_documents() -> list[dict[str, Any]] | None:
    """Fetch documents belonging to the authenticated user."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/documents",
            headers=get_auth_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return None

    if response.status_code != 200:
        st.error(get_api_error_message(response, "Could not load documents."))
        return None

    try:
        return response.json()
    except ValueError:
        st.error("The backend returned an invalid document response.")
        return None


def get_ingestion_status(document_id: str) -> dict[str, Any] | None:
    """Fetch the latest ingestion job state for one document."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/documents/{document_id}/ingestion-status",
            headers=get_auth_headers(),
            timeout=20,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        return response.json()
    except ValueError:
        return None


def show_auth_screen() -> None:
    """Render sign-in and account-creation UI."""
    st.title("Compliance RAG System")
    st.caption("Ask grounded questions about your compliance documents.")

    sign_in_tab, create_account_tab = st.tabs(["Sign in", "Create account"])
    supabase = get_supabase_client()

    with sign_in_tab:
        with st.form("sign_in_form"):
            email = st.text_input("Email", key="sign_in_email")
            password = st.text_input(
                "Password",
                type="password",
                key="sign_in_password",
            )
            submitted = st.form_submit_button("Sign in", type="primary")

        if submitted:
            if not email.strip() or not password:
                st.warning("Enter both email and password.")
                return

            try:
                response = supabase.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
                st.session_state.session = response.session
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to sign in: {exc}")

    with create_account_tab:
        with st.form("create_account_form"):
            email = st.text_input("Email", key="create_account_email")
            password = st.text_input(
                "Password",
                type="password",
                key="create_account_password",
            )
            submitted = st.form_submit_button("Create account", type="primary")

        if submitted:
            if not email.strip() or len(password) < 6:
                st.warning("Use a valid email and a password with at least 6 characters.")
                return

            try:
                response = supabase.auth.sign_up(
                    {"email": email.strip(), "password": password}
                )
                st.success(
                    "Account created. Check your email if confirmation is enabled."
                )

                if response.session:
                    st.session_state.session = response.session
                    st.rerun()
            except Exception as exc:
                st.error(f"Unable to create account: {exc}")


def upload_document(uploaded_file: Any) -> bool:
    """Send one selected document to the FastAPI upload endpoint."""
    headers = get_auth_headers()

    if not headers:
        st.error("Your session is missing. Please sign in again.")
        return False

    if uploaded_file.size > MAX_UPLOAD_SIZE_BYTES:
        st.error("File is too large. Maximum upload size is 20 MB.")
        return False

    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/documents/upload",
            headers=headers,
            files=files,
            timeout=120,
        )
    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return False

    if response.status_code == 201:
        st.success(f"Uploaded {response.json()['file_name']}. Processing has started.")
        return True

    st.error(get_api_error_message(response, "Upload failed."))
    return False


def retry_document(document_id: str) -> bool:
    """Request a new ingestion attempt for one failed document."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/documents/{document_id}/retry",
            headers=get_auth_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return False

    if response.status_code == 200:
        return True

    st.error(get_api_error_message(response, "Could not retry document processing."))
    return False


def delete_document(document_id: str) -> bool:
    """Delete one document belonging to the signed-in user."""
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/v1/documents/{document_id}",
            headers=get_auth_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return False

    if response.status_code == 204:
        return True

    st.error(get_api_error_message(response, "Could not delete document."))
    return False


def remove_duplicate_citations(
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one citation per file/page/chunk pair."""
    unique_citations = []
    seen_citations = set()

    for citation in citations:
        citation_key = (
            citation.get("file_name"),
            citation.get("page_number"),
            citation.get("chunk_index"),
        )

        if citation_key not in seen_citations:
            seen_citations.add(citation_key)
            unique_citations.append(citation)

    return unique_citations


def show_citations(citations: list[dict[str, Any]]) -> None:
    """Render evidence excerpts for the answer's citations."""
    if not citations:
        return

    st.markdown("### Sources")

    for citation in citations:
        source_number = citation.get("source_number", "?")
        file_name = citation.get("file_name", "Unknown document")
        page_number = citation.get("page_number")
        excerpt = str(citation.get("excerpt", "")).strip()
        score = citation.get("score")

        source_label = f"[{source_number}] {file_name}"

        if page_number:
            source_label += f" · page {page_number}"

        with st.expander(source_label, expanded=False):
            if score is not None:
                st.caption(f"Retrieval confidence: {float(score):.0%}")

            if excerpt:
                st.caption("Supporting excerpt")
                st.write(excerpt)
            else:
                st.info("No preview is available for this source.")


def show_rag_question_answering(processed_document_count: int) -> None:
    """Render grounded question answering with source citations."""
    st.divider()
    st.subheader("Ask your documents")
    st.caption(
        "Answers are generated only from retrieved document evidence and include sources."
    )

    if processed_document_count == 0:
        st.info("Upload and process at least one document before asking a question.")
        return

    with st.form("rag_question_form", clear_on_submit=False):
        question = st.text_area(
            "Ask a compliance question",
            placeholder="Example: Who may access customer data?",
            key="rag_question",
            height=100,
        )
        submitted = st.form_submit_button("Get grounded answer", type="primary")

    if not submitted:
        return

    cleaned_question = question.strip()

    if len(cleaned_question) < 3:
        st.warning("Enter at least 3 characters.")
        return

    try:
        with st.spinner("Retrieving evidence and generating answer..."):
            response = requests.post(
                f"{BACKEND_URL}/api/v1/rag/ask",
                headers=get_auth_headers(),
                json={"question": cleaned_question, "top_k": 5},
                timeout=120,
            )
    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return

    if response.status_code != 200:
        st.error(get_api_error_message(response, "Could not generate an answer."))
        return

    try:
        answer_data = response.json()
    except ValueError:
        st.error("The backend returned an invalid answer response.")
        return

    answer = str(answer_data.get("answer", "")).strip()
    citations = remove_duplicate_citations(answer_data.get("citations", []))

    st.markdown("### Answer")

    if answer == NOT_FOUND_ANSWER or not citations:
        st.info(answer or NOT_FOUND_ANSWER)
        return

    st.write(answer)
    show_citations(citations)


def show_document_status(document: dict[str, Any]) -> None:
    """Render status and latest processing stage for one document."""
    document_status = document.get("status", "uploaded")
    status_label = STATUS_LABELS.get(document_status, document_status.title())

    if document_status == "processed":
        st.success(f"Status: {status_label}")
        return

    if document_status == "failed":
        st.error(f"Status: {status_label}")
        error_message = document.get("error_message") or "Document processing failed."
        st.caption(error_message)
        return

    job = get_ingestion_status(str(document["id"]))

    if document_status == "uploaded":
        st.info(f"Status: {status_label}")
    else:
        st.warning(f"Status: {status_label}")

    if not job:
        st.caption("Waiting for ingestion status...")
        return

    stage = job.get("processing_stage") or "queued"
    stage_label = STAGE_LABELS.get(stage, stage.title())
    attempt_count = job.get("attempt_count", 0)

    st.caption(f"{stage_label} · Attempt {attempt_count}")

    if job.get("error_message"):
        st.caption(f"Latest job message: {job['error_message']}")


def show_document_list(documents: list[dict[str, Any]]) -> None:
    """Render the user's uploaded documents and document actions."""
    st.subheader("My documents")

    if not documents:
        st.info("No documents uploaded yet.")
        return

    for document in documents:
        action_columns = st.columns([6, 1, 1])

        with action_columns[0]:
            st.markdown(f"**{document['file_name']}**")

            details = [
                document.get("mime_type", "Unknown type"),
                format_file_size(document.get("file_size_bytes")),
            ]

            if document.get("page_count"):
                details.append(f"{document['page_count']} page(s)")

            if document.get("created_at"):
                details.append(f"Uploaded {format_created_at(document['created_at'])}")

            st.caption(" · ".join(details))
            show_document_status(document)

        with action_columns[1]:
            if document.get("status") == "failed":
                if st.button("Retry", key=f"retry_document_{document['id']}"):
                    if retry_document(str(document["id"])):
                        st.success("Retry queued.")
                        st.rerun()

        with action_columns[2]:
            if st.button("Delete", key=f"delete_document_{document['id']}"):
                if delete_document(str(document["id"])):
                    st.success("Document deleted.")
                    st.rerun()

        st.divider()


def schedule_document_status_refresh(documents: list[dict[str, Any]]) -> None:
    """Refresh the UI while one or more documents are being ingested."""
    has_pending_document = any(
        document.get("status") in PENDING_DOCUMENT_STATUSES
        for document in documents
    )

    if not has_pending_document:
        return

    st.caption("Refreshing document status automatically...")
    time.sleep(3)
    st.rerun()


def show_document_dashboard() -> None:
    """Render the authenticated document dashboard."""
    session = st.session_state.session
    user = session.user

    st.title("Compliance RAG System")
    st.caption("Upload compliance documents and ask grounded questions with evidence.")

    left, right = st.columns([4, 1])

    with left:
        st.write(f"Signed in as **{user.email}**")

    with right:
        if st.button("Sign out"):
            get_supabase_client().auth.sign_out()
            st.session_state.pop("session", None)
            st.rerun()

    st.divider()
    st.subheader("Upload a document")
    st.caption("PDF, DOCX, TXT, CSV, XLSX · Maximum size: 20 MB")

    uploaded_file = st.file_uploader(
        "Choose a compliance document",
        type=ALLOWED_TYPES,
        label_visibility="collapsed",
    )

    if uploaded_file:
        st.caption(
            f"Selected: {uploaded_file.name} · {format_file_size(uploaded_file.size)}"
        )

    if uploaded_file and st.button("Upload document", type="primary"):
        if upload_document(uploaded_file):
            st.rerun()

    st.divider()

    documents = get_documents()

    if documents is None:
        return

    show_document_list(documents)

    processed_document_count = sum(
        document.get("status") == "processed"
        for document in documents
    )

    show_rag_question_answering(processed_document_count)
    schedule_document_status_refresh(documents)


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(
        page_title="Compliance RAG System",
        page_icon="📚",
        layout="centered",
    )

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY in your environment.")
        return

    if "session" not in st.session_state:
        show_auth_screen()
        return

    show_document_dashboard()


if __name__ == "__main__":
    main()
