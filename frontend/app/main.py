import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def get_supabase_client() -> Client:
    """Create a Supabase client using the public anonymous key."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        raise RuntimeError(
            "Supabase frontend configuration is missing. "
            "Set SUPABASE_URL and SUPABASE_ANON_KEY in .env."
        )

    return create_client(supabase_url, supabase_anon_key)


def initialize_session_state() -> None:
    """Create session-state keys used by the frontend."""
    defaults = {
        "access_token": None,
        "user_email": None,
        "user_id": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_backend_profile(access_token: str) -> dict:
    """Call the protected FastAPI profile endpoint."""
    response = requests.get(
        f"{BACKEND_URL}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def show_auth_page(supabase: Client) -> None:
    """Render signup and login forms."""
    st.title("Compliance RAG System")
    st.caption("Ask questions about your compliance documents with evidence.")

    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])

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
            if not email or not password:
                st.error("Enter both email and password.")
                return

            try:
                response = supabase.auth.sign_in_with_password(
                    {
                        "email": email,
                        "password": password,
                    }
                )

                if response.session is None or response.user is None:
                    st.error("Sign in failed. Please try again.")
                    return

                st.session_state.access_token = response.session.access_token
                st.session_state.user_email = response.user.email
                st.session_state.user_id = response.user.id

                st.success("Signed in successfully.")
                st.rerun()

            except Exception:
                st.error("Unable to sign in. Check your email and password.")

    with sign_up_tab:
        with st.form("sign_up_form"):
            email = st.text_input("Email", key="sign_up_email")
            password = st.text_input(
                "Password",
                type="password",
                key="sign_up_password",
                help="Use at least 6 characters.",
            )
            submitted = st.form_submit_button("Create account")

        if submitted:
            if not email or not password:
                st.error("Enter both email and password.")
                return

            if len(password) < 6:
                st.error("Password must contain at least 6 characters.")
                return

            try:
                response = supabase.auth.sign_up(
                    {
                        "email": email,
                        "password": password,
                    }
                )

                if response.user is None:
                    st.error("Account creation failed. Please try again.")
                    return

                if response.session is None:
                    st.success(
                        "Account created. Check your email and confirm your account "
                        "before signing in."
                    )
                    return

                st.session_state.access_token = response.session.access_token
                st.session_state.user_email = response.user.email
                st.session_state.user_id = response.user.id

                st.success("Account created and signed in successfully.")
                st.rerun()

            except Exception:
                st.error("Unable to create account. Try a different email.")


def show_dashboard() -> None:
    """Render the temporary authenticated screen."""
    st.title("Compliance RAG System")
    st.success(f"Signed in as {st.session_state.user_email}")

    st.subheader("Backend token validation")

    try:
        profile = get_backend_profile(st.session_state.access_token)

        st.success("FastAPI successfully validated your Supabase access token.")
        st.json(profile)

    except requests.RequestException:
        st.error(
            "FastAPI could not validate the session. "
            "Make sure the backend is running on http://localhost:8000."
        )

    st.info(
        "Authentication works. The document upload dashboard will be added next."
    )

    if st.button("Sign out"):
        st.session_state.access_token = None
        st.session_state.user_email = None
        st.session_state.user_id = None
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Compliance RAG System",
        page_icon="📚",
    )

    initialize_session_state()
    supabase = get_supabase_client()

    if st.session_state.access_token:
        show_dashboard()
    else:
        show_auth_page(supabase)


if __name__ == "__main__":
    main()