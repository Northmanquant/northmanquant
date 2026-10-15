def _live_strip_impl(symbol: str, exchange: str, interval: str, dec: int, extra: dict | None = None) -> None:
    """
    Live ticker strip — built entirely with Streamlit native widgets so it
    re-renders safely inside `st.fragment` (raw HTML in fragments gets
    escaped, which is what was showing <b>+25</b> as plain text).
    """
    import time as _t

    tick = fetch_tick(exchange, symbol)
    state = st.session_state.get("nq_state") or {}
    score = st.session_state.get("nq_score")
    prev = st.session_state.get("nq_last_price")
    price = tick["price"] if tick else None

    # direction arrow based on price change
    if price is not None and prev:
        if price > prev:
            st.session_state["nq_arrow"] = "up"
        elif price < prev:
            st.session_state["nq_arrow"] = "down"
    if price is not None:
        st.session_state["nq_last_price"] = price

    minutes = INTERVAL_MINUTES.get(interval, 60)
    left = minutes * 60 - (int(_t.time()) % (minutes * 60))
    progress = max(0, min(100, int((1 - left / (minutes * 60)) * 100)))
    countdown = f"{left // 60:02d}:{left % 60:02d}"

    # position PnL
    pnl = None
    if state.get("status") in ("long", "short") and state.get("entry") and price:
        entry = float(state["entry"])
        pnl = (price - entry) / entry * 100 * (1 if state["status"] == "long" else -1)

    cols = st.columns([1.4, 1.3, 1.6, 1.0, 1.0, 0.9], gap="small")

    with cols[0]:
        st.markdown(
            f"<span style='color:#a5f3fc;font-size:11px;font-weight:700'>"
            f"<span class='nq-live-dot'></span> LIVE · زنده</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<span class='nq-glow' style='font-family:ui-monospace,monospace;font-size:26px;"
            f"font-weight:800;color:#f8fafc'>{price:,.{dec}f if price is not None else 0}f</span>",
            unsafe_allow_html=True,
        )

    with cols[1]:
        if tick and tick.get("bid"):
            b, a = tick["bid"], tick["ask"]
            st.markdown(
                f"<div style='font-family:ui-monospace,monospace;font-size:11px;color:#94a3b8'>"
                f"Bid <b style='color:#34d399'>{b:,.{dec}f}</b></div>"
                f"<div style='font-family:ui-monospace,monospace;font-size:11px;color:#94a3b8'>"
                f"Ask <b style='color:#fb7185'>{a:,.{dec}f}</b></div>",
                unsafe_allow_html=True,
            )
        elif price is not None:
            st.caption("bid/ask در دسترس نیست")

    with cols[2]:
        if score is not None:
            tone = "#34d399" if score >= 0 else "#fb7185"
            st.markdown(
                f"<div style='font-size:11px;color:#94a3b8;font-family:ui-monospace,monospace'>"
                f"امتیاز همگرایی</div>"
                f"<div style='font-size:22px;font-weight:800;color:{tone};"
                f"font-family:ui-monospace,monospace;line-height:1.1'>{score:+.0f}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("امتیاز: —")

    with cols[3]:
        if pnl is not None and state.get("status"):
            label = "🟢 لانگ" if state["status"] == "long" else "🔴 شورت"
            tone = "#34d399" if pnl >= 0 else "#fb7185"
            st.markdown(
                f"<div style='font-size:11px;color:#94a3b8'>پوزیشن فعال</div>"
                f"<div style='font-size:12px;font-weight:700'>{label}</div>"
                f"<div style='font-size:18px;font-weight:800;color:{tone};"
                f"font-family:ui-monospace,monospace;line-height:1.1'>{pnl:+.2f}%</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:11px;color:#94a3b8'>خارج از بازار</div>"
                "<div style='font-size:18px;font-weight:800;color:#475569;"
                "font-family:ui-monospace,monospace'>—</div>",
                unsafe_allow_html=True,
            )

    with cols[4]:
        if extra:
            parts = []
            if extra.get("mark"):
                parts.append(
                    f"<div style='font-size:11px;color:#94a3b8'>Mark "
                    f"<b style='color:#a5b4fc;font-family:ui-monospace,monospace'>"
                    f"{extra['mark']:,.{dec}f}</b></div>"
                )
            if extra.get("open_interest") is not None:
                parts.append(
                    f"<div style='font-size:11px;color:#94a3b8'>OI "
                    f"<b style='color:#fbbf24;font-family:ui-monospace,monospace'>"
                    f"{extra['open_interest']:,.2f}</b></div>"
                )
            if parts:
                st.markdown("".join(parts), unsafe_allow_html=True)
            else:
                st.caption("—")
        else:
            st.caption("—")

    with cols[5]:
        st.markdown(
            f"<div style='text-align:center;font-family:ui-monospace,monospace'>"
            f"<div style='font-size:12px;color:#cbd5e1'>⏳ {countdown}</div></div>",
            unsafe_allow_html=True,
        )
        st.progress(progress, text=None)
        st.caption("<span style='font-size:9px;color:#64748b'>تا بستن کندل</span>", unsafe_allow_html=True)


try:
    live_strip_auto = st.fragment(run_every=5)(_live_strip_impl)
    live_strip_manual = st.fragment(_live_strip_impl)
except Exception:  # older Streamlit without fragment auto-rerun
    live_strip_auto = _live_strip_impl  # type: ignore
    live_strip_manual = _live_strip_impl  # type: ignore
