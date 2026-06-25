import os
import time
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

ALLOWED_TYPES = ["pdf", "docx", "txt", "csv", "xlsx"]
NOT_FOUND_ANSWER = "I could not find an answer in your uploaded documents."
PENDING_DOCUMENT_STATUSES = {"uploaded", "processing"}


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
        st.error(
            get_api_error_message(
                response,
                "Could not load documents.",
            )
        )
        return None

    try:
        return response.json()
    except ValueError:
        st.error("The backend returned an invalid document response.")
        return None


def show_auth_screen() -> None:
    """Render sign-in and account-creation UI."""
    st.title("Compliance RAG System")
    st.caption("Ask questions about your compliance documents with evidence.")

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
            submitted = st.form_submit_button("Sign in")

        if submitted:
            try:
                response = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
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
            submitted = st.form_submit_button("Create account")

        if submitted:
            try:
                response = supabase.auth.sign_up(
                    {"email": email, "password": password}
                )
                st.success(
                    "Account created. Check your email if confirmation is enabled, "
                    "then sign in."
                )

                if response.session:
                    st.session_state.session = response.session
                    st.rerun()
            except Exception as exc:
                st.error(f"Unable to create account: {exc}")


def upload_document(uploaded_file: Any) -> None:
    """Send one selected document to the FastAPI upload endpoint."""
    headers = get_auth_headers()

    if not headers:
        st.error("Your session is missing. Please sign in again.")
        return

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

        if response.status_code == 201:
            st.success(f"Uploaded: {response.json()['file_name']}")
            st.rerun()
            return

        st.error(
            get_api_error_message(
                response,
                "Upload failed.",
            )
        )

    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")


def retry_document(document_id: str) -> bool:
    """Request a new ingestion attempt for one failed document."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/documents/{document_id}/retry",
            headers=get_auth_headers(),
            timeout=30,
        )

        if response.status_code == 200:
            return True

        st.error(
            get_api_error_message(
                response,
                "Could not retry document processing.",
            )
        )
        return False

    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return False


def delete_document(document_id: str) -> bool:
    """Delete one document belonging to the signed-in user."""
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/v1/documents/{document_id}",
            headers=get_auth_headers(),
            timeout=30,
        )

        if response.status_code == 204:
            return True

        st.error(
            get_api_error_message(
                response,
                "Could not delete document.",
            )
        )
        return False

    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return False


def remove_duplicate_citations(
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one citation per file/chunk pair."""
    unique_citations = []
    seen_citations = set()

    for citation in citations:
        citation_key = (
            citation.get("file_name"),
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
        excerpt = citation.get("excerpt", "").strip()

        with st.expander(f"[{source_number}] {file_name}", expanded=False):
            if excerpt:
                st.caption("Supporting excerpt")
                st.write(excerpt)
            else:
                st.info("No preview is available for this source.")


def show_rag_question_answering(
    processed_document_count: int,
) -> None:
    """Render grounded question answering with source citations."""
    st.divider()
    st.subheader("Ask my documents")
    st.caption(
        "Answers are generated only from retrieved document evidence "
        "and include supporting excerpts."
    )

    if processed_document_count == 0:
        st.info(
            "Upload and process at least one document before asking a question."
        )
        return

    with st.form("rag_question_form", clear_on_submit=False):
        question = st.text_area(
            "Ask a compliance question",
            placeholder="Example: Who may access customer data?",
            key="rag_question",
            height=100,
        )
        submitted = st.form_submit_button(
            "Get grounded answer",
            type="primary",
        )

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
                json={
                    "question": cleaned_question,
                    "top_k": 5,
                },
                timeout=120,
            )
    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return

    if response.status_code != 200:
        st.error(
            get_api_error_message(
                response,
                "Could not generate an answer.",
            )
        )
        return

    try:
        answer_data = response.json()
    except ValueError:
        st.error("The backend returned an invalid answer response.")
        return

    answer = str(answer_data.get("answer", "")).strip()
    citations = remove_duplicate_citations(
        answer_data.get("citations", [])
    )

    st.markdown("### Answer")

    if answer == NOT_FOUND_ANSWER or not citations:
        st.info(answer or NOT_FOUND_ANSWER)
        return

    st.write(answer)
    show_citations(citations)


def show_document_list(documents: list[dict[str, Any]]) -> None:
    """Render the user's uploaded documents and document actions."""
    st.subheader("My documents")

    if not documents:
        st.info("No documents uploaded yet.")
        return

    for document in documents:
        action_columns = st.columns([5, 1, 1])

        with action_columns[0]:
            st.markdown(f"**{document['file_name']}**")
            st.caption(
                f"{document['mime_type']} · "
                f"{document['file_size_bytes']} bytes · "
                f"Status: {document['status']}"
            )

            if document["status"] == "uploaded":
                st.info("Queued for processing.")

            if document["status"] == "processing":
                st.info("Processing document...")

            if document["status"] == "failed":
                error_message = document.get(
                    "error_message",
                    "Document processing failed.",
                )
                st.error(error_message)

        with action_columns[1]:
            if document["status"] == "failed":
                if st.button(
                    "Retry",
                    key=f"retry_document_{document['id']}",
                ):
                    if retry_document(document["id"]):
                        st.success("Retry queued.")
                        st.rerun()

        with action_columns[2]:
            if st.button(
                "Delete",
                key=f"delete_document_{document['id']}",
            ):
                if delete_document(document["id"]):
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

    time.sleep(2)
    st.rerun()


def show_document_dashboard() -> None:
    """Render the authenticated document dashboard."""
    session = st.session_state.session
    user = session.user

    st.title("Compliance RAG System")
    st.caption(
        "Upload compliance documents and ask grounded questions with evidence."
    )

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

    uploaded_file = st.file_uploader(
        "Supported formats: PDF, DOCX, TXT, CSV, XLSX · Maximum size: 20 MB",
        type=ALLOWED_TYPES,
    )

    if uploaded_file and st.button("Upload document"):
        upload_document(uploaded_file)

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

    if "session" not in st.session_state:
        show_auth_screen()
        return

    show_document_dashboard()


if __name__ == "__main__":
    main()