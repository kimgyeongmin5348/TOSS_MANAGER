"""Conditional-order management UI with explicit live-order safeguards."""

from __future__ import annotations

from datetime import date, timedelta
import os
from uuid import uuid4

import streamlit as st

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.conditional_orders import build_condition, build_conditional_order


def _live_enabled() -> bool:
    return os.getenv("TOSS_LIVE_CONDITIONAL_ORDERS_ENABLED", "false").lower() in {"1", "true", "yes"}


def _items(result: object) -> list[dict]:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("orders", "items", "conditionalOrders"):
            value = result.get(key)
            if isinstance(value, list):
                return value
    return []


def _render_list(client: TossAPIClient, account_seq: int) -> None:
    status = st.radio("조회 범위", ["진행 중", "종료"], horizontal=True)
    api_status = "OPEN" if status == "진행 중" else "CLOSED"
    try:
        orders = _items(client.get_conditional_orders(account_seq, status=api_status))
    except TossAPIError as exc:
        st.error(f"조건주문을 불러오지 못했습니다. {exc}")
        return
    if not orders:
        st.info("해당 조건주문이 없습니다.")
        return
    for order in orders:
        order_id = str(order.get("conditionalOrderId", ""))
        with st.expander(
            f"{order.get('symbol', '-')} · {order.get('type', '-')} · {order.get('status', '-')}",
        ):
            st.json(order)
            if api_status == "OPEN" and order_id:
                confirmation = st.text_input(
                    "취소하려면 주문 ID를 그대로 입력하세요.", key=f"cancel_text_{order_id}"
                )
                if st.button("조건주문 취소", key=f"cancel_{order_id}", type="secondary"):
                    if not _live_enabled():
                        st.error("실주문 기능이 잠겨 있습니다. .env 설정을 확인해 주세요.")
                    elif confirmation != order_id:
                        st.error("주문 ID가 일치하지 않습니다.")
                    else:
                        try:
                            client.cancel_conditional_order(account_seq, order_id)
                        except TossAPIError as exc:
                            st.error(f"취소에 실패했습니다. {exc}")
                        else:
                            st.success("조건주문을 취소했습니다.")
                            st.rerun()


def _condition_fields(prefix: str, *, side_options: list[str], order_type: str) -> tuple[str, str, str | None]:
    side = st.selectbox("매매 방향", side_options, key=f"{prefix}_side")
    trigger = st.text_input("감시가", key=f"{prefix}_trigger")
    price = st.text_input("주문가", key=f"{prefix}_price", disabled=order_type == "MARKET")
    return side, trigger, price if order_type == "LIMIT" else None


def _render_editor(client: TossAPIClient, account_seq: int) -> None:
    action = st.radio("작업", ["새로 등록", "기존 주문 수정"], horizontal=True)
    modifying = action == "기존 주문 수정"
    conditional_id = st.text_input("수정할 조건주문 ID") if modifying else ""
    symbol = st.text_input("종목 코드", placeholder="예: 005930, NVDA", disabled=modifying)
    kind = st.selectbox("조건 유형", ["SINGLE", "OCO", "OTO"])
    order_type = st.selectbox(
        "주문 유형", ["LIMIT", "MARKET"], disabled=kind in {"OCO", "OTO"}
    )
    if kind in {"OCO", "OTO"}:
        order_type = "LIMIT"
    quantity = st.text_input("수량", placeholder="예: 1 또는 0.5")
    expiry = st.date_input("만료일", value=date.today() + timedelta(days=30), min_value=date.today())

    st.markdown("첫 번째 조건")
    first_sides = ["SELL"] if kind == "OCO" else ["BUY"] if kind == "OTO" else ["BUY", "SELL"]
    first_values = _condition_fields("first", side_options=first_sides, order_type=order_type)
    second_values = None
    if kind != "SINGLE":
        st.markdown("두 번째 조건")
        second_values = _condition_fields("second", side_options=["SELL"], order_type=order_type)
    high_value = st.checkbox("1억 원 이상 주문 가능성을 확인했습니다.")
    try:
        first = build_condition(*first_values, order_type)
        second = build_condition(*second_values, order_type) if second_values else None
        client_order_id = st.session_state.setdefault("conditional_client_order_id", f"porto-{uuid4().hex[:24]}")
        payload = build_conditional_order(
            symbol=None if modifying else symbol,
            order_kind=kind,
            quantity=quantity,
            order_type=order_type,
            expire_date=expiry,
            first=first,
            second=second,
            client_order_id=None if modifying else client_order_id,
            confirm_high_value=high_value,
        )
    except ValueError as exc:
        st.caption(f"입력 확인: {exc}")
        payload = None

    st.markdown("주문 미리보기")
    st.json(payload or {})
    st.warning("조건 충족 시 실제 주문이 자동 생성됩니다. 감시가·주문가·수량을 다시 확인하세요.")
    phrase = "수정 실행" if modifying else "주문 등록"
    typed = st.text_input(f"최종 실행하려면 `{phrase}`을 입력하세요.")
    if st.button(phrase, type="primary", disabled=payload is None):
        if not _live_enabled():
            st.error("실주문 기능이 잠겨 있습니다. `.env`에서 명시적으로 활성화해야 합니다.")
            return
        if typed != phrase:
            st.error("확인 문구가 일치하지 않습니다.")
            return
        if modifying and not conditional_id.strip():
            st.error("수정할 조건주문 ID를 입력해 주세요.")
            return
        try:
            if modifying:
                result = client.modify_conditional_order(account_seq, conditional_id.strip(), payload)
                message = "수정했습니다. 수정 후 발급된 새 주문 ID를 사용하세요."
            else:
                result = client.create_conditional_order(account_seq, payload)
                message = "조건주문을 등록했습니다."
        except TossAPIError as exc:
            st.error(f"요청에 실패했습니다. 재시도 전에 주문 목록에서 접수 여부를 확인하세요. {exc}")
        else:
            st.success(message)
            st.json(result)
            st.session_state.conditional_client_order_id = f"porto-{uuid4().hex[:24]}"


def render_conditional_orders(client: TossAPIClient, account_seq: int) -> None:
    st.title("조건주문")
    st.caption("토스증권이 가격을 감시하고 조건 충족 시 실제 주문을 생성합니다.")
    if not _live_enabled():
        st.info("현재 조회·미리보기 모드입니다. 실주문 등록·수정·취소는 잠겨 있습니다.")
    list_tab, editor_tab = st.tabs(["주문 조회", "등록·수정"])
    with list_tab:
        _render_list(client, account_seq)
    with editor_tab:
        _render_editor(client, account_seq)
