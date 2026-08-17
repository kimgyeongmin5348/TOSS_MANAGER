"""Password, email, linked account, privacy, and withdrawal controls."""

from __future__ import annotations

import logging

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.accounts import (
    change_password,
    confirm_email_verification,
    create_email_verification,
    delete_user_data,
    disconnect_account,
    list_linked_accounts,
)
from toss_manager.mailer import send_account_token
from toss_manager.config import MailSettings
from toss_manager.session import logout


LOGGER = logging.getLogger(__name__)


def render_account_view(engine: Engine, user_id: int) -> None:
    st.title("계정 관리")
    st.caption("로그인 보안, 이메일 인증, 연결 계좌와 개인정보를 관리합니다.")

    security, accounts, privacy = st.tabs(["로그인 보안", "연결 계좌", "개인정보·탈퇴"])
    with security:
        _render_password_change(engine, user_id)
        if MailSettings.from_env().configured:
            st.divider()
            _render_email_verification(engine, user_id)
    with accounts:
        _render_linked_accounts(engine, user_id)
    with privacy:
        _render_privacy_and_withdrawal(engine, user_id)


def _render_password_change(engine: Engine, user_id: int) -> None:
    st.subheader("비밀번호 변경")
    with st.form("change_password"):
        current = st.text_input("현재 비밀번호", type="password")
        new = st.text_input("새 비밀번호 (8자 이상)", type="password")
        confirmation = st.text_input("새 비밀번호 확인", type="password")
        submitted = st.form_submit_button("비밀번호 변경", use_container_width=True)
    if not submitted:
        return
    if new != confirmation:
        st.error("새 비밀번호 확인이 일치하지 않습니다.")
        return
    try:
        change_password(engine, user_id=user_id, current_password=current, new_password=new)
    except ValueError as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        LOGGER.exception("Password change database failure")
        st.error("비밀번호를 변경하지 못했습니다. 잠시 후 다시 시도해 주세요.")
    else:
        logout(notice="비밀번호가 변경되었습니다. 새 비밀번호로 다시 로그인해 주세요.")


def _render_email_verification(engine: Engine, user_id: int) -> None:
    verified = bool(st.session_state.get("email_verified"))
    st.subheader("이메일 인증")
    if verified:
        st.success("이메일 인증이 완료되었습니다.")
        return
    st.info("이메일 인증 코드는 30분 동안 유효하며 한 번만 사용할 수 있습니다.")
    if st.button("인증 코드 보내기", use_container_width=True):
        try:
            email, token = create_email_verification(engine, user_id=user_id)
            if send_account_token(recipient=email, token=token, purpose="verify"):
                st.success("인증 코드를 이메일로 보냈습니다.")
            else:
                st.warning("메일 발송 설정이 없어 코드를 보내지 못했습니다. 관리자에게 문의해 주세요.")
        except (SQLAlchemyError, OSError):
            LOGGER.exception("Email verification delivery failure")
            st.error("인증 코드를 보내지 못했습니다. 잠시 후 다시 시도해 주세요.")
    with st.form("verify_email"):
        token = st.text_input("인증 코드")
        submitted = st.form_submit_button("이메일 인증 완료", use_container_width=True)
    if submitted:
        try:
            if confirm_email_verification(engine, user_id=user_id, token=token):
                st.session_state.email_verified = True
                st.success("이메일 인증이 완료되었습니다.")
                st.rerun()
            else:
                st.error("인증 코드가 올바르지 않거나 만료되었습니다.")
        except SQLAlchemyError:
            LOGGER.exception("Email verification database failure")
            st.error("이메일 인증 상태를 저장하지 못했습니다.")


def _render_linked_accounts(engine: Engine, user_id: int) -> None:
    st.subheader("연결된 계좌")
    st.caption("연결을 해제해도 과거 스냅샷은 보존됩니다. 다시 연결하면 활성화됩니다.")
    try:
        accounts = list_linked_accounts(engine, user_id=user_id)
    except SQLAlchemyError:
        LOGGER.exception("Linked account read failure")
        st.error("연결된 계좌를 불러오지 못했습니다.")
        return
    if not accounts:
        st.info("연결된 계좌가 없습니다.")
        return
    for account in accounts:
        label = f"{account.get('account_no_masked') or '계좌'} · {account.get('account_type') or '토스증권'}"
        content, action = st.columns([4, 1])
        content.write(label)
        content.caption("활성" if account["is_active"] else "연결 해제됨")
        if account["is_active"] and action.button(
            "연결 해제", key=f"disconnect_{account['account_id']}"
        ):
            try:
                disconnect_account(engine, user_id=user_id, account_id=int(account["account_id"]))
                # A disconnected account must not remain queryable through this live session.
                st.session_state.pop("client", None)
                st.session_state.pop("accounts", None)
                st.success("계좌 연결을 해제했습니다.")
                st.rerun()
            except (SQLAlchemyError, ValueError):
                LOGGER.exception("Account disconnect failure")
                st.error("계좌 연결을 해제하지 못했습니다.")


def _render_privacy_and_withdrawal(engine: Engine, user_id: int) -> None:
    st.subheader("개인정보 처리 안내")
    st.markdown(
        "- 저장: 이메일, 암호화된 비밀번호 해시, 마스킹 계좌번호, 스냅샷, 관심종목\n"
        "- 미저장: 토스 Client ID와 Client Secret은 현재 세션에만 유지\n"
        "- 탈퇴 시 삭제: 사용자, 연결 계좌, 포트폴리오 스냅샷, 관심종목\n"
        "- 탈퇴 후 보존: 종목·캔들·뉴스·재무 같은 사용자 식별자가 없는 공용 시장 데이터"
    )
    st.divider()
    st.subheader("회원탈퇴")
    st.warning("탈퇴한 사용자 데이터는 앱에서 복구할 수 없습니다.")
    with st.form("withdraw_account"):
        password = st.text_input("현재 비밀번호", type="password", key="withdraw_password")
        confirmation = st.text_input("확인을 위해 DELETE 입력")
        submitted = st.form_submit_button("회원탈퇴 및 개인정보 삭제", use_container_width=True)
    if not submitted:
        return
    if confirmation != "DELETE":
        st.error("확인 문구가 일치하지 않습니다.")
        return
    try:
        delete_user_data(engine, user_id=user_id, password=password)
    except ValueError as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        LOGGER.exception("User deletion database failure")
        st.error("회원탈퇴를 처리하지 못했습니다. 데이터는 삭제되지 않았습니다.")
    else:
        logout(notice="회원탈퇴가 완료되었고 개인 데이터가 삭제되었습니다.")
