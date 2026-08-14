"""Validation and payload construction for Toss conditional orders."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any, field: str) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}은 숫자여야 합니다.") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{field}은 0보다 커야 합니다.")
    return format(number.normalize(), "f")


def build_condition(side: str, trigger_price: Any, order_price: Any | None, order_type: str) -> dict[str, str]:
    if side not in {"BUY", "SELL"}:
        raise ValueError("매매 방향은 BUY 또는 SELL이어야 합니다.")
    condition = {"orderSide": side, "triggerPrice": _decimal(trigger_price, "감시가")}
    if order_type == "LIMIT":
        condition["orderPrice"] = _decimal(order_price, "주문가")
    elif order_type != "MARKET":
        raise ValueError("주문 유형은 LIMIT 또는 MARKET이어야 합니다.")
    return condition


def build_conditional_order(
    *,
    symbol: str | None,
    order_kind: str,
    quantity: Any,
    order_type: str,
    expire_date: date,
    first: dict[str, Any],
    second: dict[str, Any] | None = None,
    client_order_id: str | None = None,
    confirm_high_value: bool = False,
) -> dict[str, Any]:
    """Build the canonical Toss request and enforce cross-field rules."""
    if order_kind not in {"SINGLE", "OCO", "OTO"}:
        raise ValueError("지원하지 않는 조건주문 종류입니다.")
    if expire_date < date.today():
        raise ValueError("만료일은 오늘 이후여야 합니다.")
    if order_kind in {"OCO", "OTO"} and order_type != "LIMIT":
        raise ValueError("OCO와 OTO는 지정가 주문만 지원합니다.")
    if order_kind == "OCO" and (first["orderSide"] != "SELL" or not second or second["orderSide"] != "SELL"):
        raise ValueError("OCO의 두 조건은 모두 매도여야 합니다.")
    if order_kind == "OTO" and (first["orderSide"] != "BUY" or not second or second["orderSide"] != "SELL"):
        raise ValueError("OTO는 첫 조건이 매수, 두 번째 조건이 매도여야 합니다.")
    if order_kind == "SINGLE" and second is not None:
        raise ValueError("SINGLE에는 두 번째 조건을 넣을 수 없습니다.")

    payload: dict[str, Any] = {
        "type": order_kind,
        "quantity": _decimal(quantity, "수량"),
        "orderType": order_type,
        "expireDate": expire_date.isoformat(),
        "first": first,
        "confirmHighValueOrder": bool(confirm_high_value),
    }
    if symbol is not None:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("종목 코드를 입력해 주세요.")
        payload["symbol"] = normalized
    if second is not None:
        payload["second"] = second
    if client_order_id:
        payload["clientOrderId"] = client_order_id
    return payload
