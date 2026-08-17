"""Data-basis and persistence status presentation."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st


def format_kst(value: Any) -> str:
    if not value:
        return "없음"
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value, timezone.utc)
    elif isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d %H:%M:%S KST")
    return str(value)


def render_snapshot_status(
    *,
    live_queried_at: datetime | None,
    latest_db: dict[str, Any] | None,
    save_state: dict[str, Any] | None,
    live: bool,
) -> None:
    status = (save_state or {}).get("message") or (
        "저장 기록 있음" if latest_db else "저장 기록 없음"
    )
    live_text = format_kst(live_queried_at)
    saved_text = format_kst(latest_db.get("saved_at") if latest_db else None)
    state_class = (
        "failed" if (save_state or {}).get("status") == "failed"
        else "success" if latest_db else "neutral"
    )
    metadata = ""
    if latest_db:
        metadata = (
            f"데이터 기준 {format_kst(latest_db.get('captured_at'))} · "
            f"{latest_db.get('snapshot_type', 'INTRADAY')} · "
            f"{latest_db.get('save_reason', 'AUTO')}"
        )
    st.markdown(
        f"""
        <style>
        .snapshot-strip{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
          gap:0;border:1px solid #e5e9f0;border-radius:12px;background:#fff;
          margin:.25rem 0 .55rem;overflow:hidden}}
        .snapshot-cell{{min-width:0;padding:.62rem .85rem;border-right:1px solid #eef0f4}}
        .snapshot-cell:nth-child(3){{border-right:0}}
        .snapshot-cell span{{display:block;color:#818896;font-size:.62rem;
          font-weight:650;margin-bottom:.16rem}}
        .snapshot-cell b{{display:block;color:#263247;font-size:.82rem;
          font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
        .snapshot-cell.state b:before{{content:"";display:inline-block;width:6px;height:6px;
          border-radius:50%;margin-right:.4rem;vertical-align:.08rem;background:#9aa1ad}}
        .snapshot-cell.state.success b:before{{background:#28a46b}}
        .snapshot-cell.state.failed b:before{{background:#e0525d}}
        .snapshot-meta{{grid-column:1/-1;padding:.4rem .85rem;border-top:1px solid #f0f2f5;
          color:#8b919c;font-size:.61rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
        @media(max-width:700px){{
          .snapshot-strip{{grid-template-columns:1fr}}
          .snapshot-cell{{border-right:0;border-bottom:1px solid #eef0f4}}
          .snapshot-cell:nth-child(3){{border-bottom:0}}
        }}
        </style>
        <div class="snapshot-strip">
          <div class="snapshot-cell"><span>마지막 실시간 조회</span>
            <b title="{escape(live_text, quote=True)}">{escape(live_text)}</b></div>
          <div class="snapshot-cell"><span>마지막 DB 저장</span>
            <b title="{escape(saved_text, quote=True)}">{escape(saved_text)}</b></div>
          <div class="snapshot-cell state {state_class}"><span>저장 상태</span>
            <b title="{escape(str(status), quote=True)}">{escape(str(status))}</b></div>
          {f'<div class="snapshot-meta">{escape(metadata)}</div>' if metadata else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if (save_state or {}).get("status") == "failed":
        st.warning("DB 저장에 실패했습니다. 실시간 조회 결과는 계속 표시됩니다. 재시도 버튼을 눌러 주세요.")

    reference = live_queried_at if live else (latest_db or {}).get("captured_at")
    if reference:
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - reference.astimezone(timezone.utc)
        stale_after = 120 if live else 24 * 3600
        if age.total_seconds() > stale_after:
            st.warning(
                "표시 중인 데이터가 오래되었습니다. "
                + ("실시간 연결 상태를 확인해 주세요." if live else "실시간 연결 후 새 스냅샷을 저장해 주세요.")
            )
