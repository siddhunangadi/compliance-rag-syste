import os

import requests
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

ALLOWED_TYPES = ["pdf", "docx", "txt", "csv", "xlsx"]


@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_auth_headers() -> dict[str, str]:
    """Build FastAPI authorization headers from the active Supabase session."""
    session = st.session_state.get("session")

    if not session:
        return {}

    return {"Authorization": f"Bearer {session.access_token}"}


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


def upload_document(uploaded_file) -> None:
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
            timeout=60,
        )

        if response.status_code == 201:
            st.success(f"Uploaded: {response.json()['file_name']}")
            st.rerun()

        detail = response.json().get("detail", "Upload failed.")
        st.error(detail)

    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")


def show_document_dashboard() -> None:
    """Render the authenticated document dashboard."""
    session = st.session_state.session
    user = session.user

    st.title("Compliance RAG System")
    st.caption("Upload compliance documents. Processing and Q&A come next.")

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

    if uploaded_file and st.button("Upload document", type="primary"):
        upload_document(uploaded_file)

    st.divider()
    st.subheader("My documents")

    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/documents",
            headers=get_auth_headers(),
            timeout=30,
        )

        if response.status_code == 200:
            documents = response.json()

            if not documents:
                st.info("No documents uploaded yet.")
                return

            for document in documents:
                st.markdown(f"**{document['file_name']}**")
                st.caption(
                    f"{document['mime_type']} · "
                    f"{document['file_size_bytes']} bytes · "
                    f"Status: {document['status']}"
                )
                st.divider()
        else:
            st.error(response.json().get("detail", "Could not load documents."))

    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")


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