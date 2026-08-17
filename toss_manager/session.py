"""One logout path and bounded Streamlit login sessions."""

from __future__ import annotations

import time

import streamlit as st

from .auth import SESSION_IDLE_MINUTES, SESSION_MAX_HOURS


def start_session(
    *, user_id: int, email: str, display_name: str | None,
    session_version: int = 1, email_verified: bool = False,
) -> None:
    now = time.time()
    st.session_state.user_id = user_id
    st.session_state.user_email = email
    st.session_state.display_name = display_name
    st.session_state.session_version = session_version
    st.session_state.email_verified = email_verified
    st.session_state.session_started_at = now
    st.session_state.session_last_activity_at = now


def session_is_valid(now: float | None = None) -> bool:
    current = now or time.time()
    started = float(st.session_state.get("session_started_at", current))
    activity = float(st.session_state.get("session_last_activity_at", current))
    valid = (
        current - activity <= SESSION_IDLE_MINUTES * 60
        and current - started <= SESSION_MAX_HOURS * 3600
    )
    if valid:
        st.session_state.session_last_activity_at = current
    return valid


def logout(*, notice: str | None = None) -> None:
    st.session_state.clear()
    if notice:
        st.session_state.auth_notice = notice
    st.rerun()


def render_logout_button(*, key: str = "logout", sidebar: bool = True) -> None:
    target = st.sidebar if sidebar else st
    if target.button("로그아웃", key=key):
        logout()
