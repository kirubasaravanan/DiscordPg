import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api_client
import auth
from ui import CATEGORICAL, PAYMENT_STATUS_TONE, api_page, format_inr, status_badge

STATUS_OPTIONS = ["", "PENDING", "PARTIAL", "OVERDUE", "PAID"]


@api_page
def render() -> None:
    st.title("Rent")

    summary = api_client.get_dashboard_summary()["rent"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Collected this month", format_inr(summary["collected_this_month"]))
    col2.metric("Pending this month", format_inr(summary["pending_this_month"]))
    col3.metric("Overdue entries", summary["overdue_count"])

    role = auth.current_role()
    can_write = role in ("OWNER", "MANAGER")

    if can_write:
        income_rows = api_client.get_income_report(months=6)["rows"]
        if income_rows:
            st.subheader("Income trend (6 months)")
            df = pd.DataFrame(income_rows)
            fig = go.Figure()
            fig.add_scatter(
                x=df["month"], y=df["rent_collected"], mode="lines+markers",
                name="Rent collected", line=dict(color=CATEGORICAL[0]),
            )
            fig.add_scatter(
                x=df["month"], y=df["expenses"], mode="lines+markers",
                name="Expenses", line=dict(color=CATEGORICAL[1]),
            )
            fig.update_layout(
                xaxis_title="Month", yaxis_title="₹", legend_title_text="",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, width="stretch")

    st.subheader("Rent ledger")
    status_filter = st.selectbox("Filter by status", STATUS_OPTIONS, format_func=lambda s: s or "All")
    ledger = api_client.list_rent_ledger(payment_status=status_filter or None)["items"]
    if not ledger:
        st.info("No rent entries match this filter.")
        return

    tenant_names = {t["id"]: t["name"] for t in api_client.list_tenants()["items"]}

    widths = [2, 1, 1, 1, 1, 1.5] + ([1.8] if can_write else [])
    header = st.columns(widths)
    for col, label in zip(header, ["**Tenant**", "**Month**", "**Rent**", "**Paid**", "**Balance**", "**Status**"]):
        col.markdown(label)
    if can_write:
        header[6].markdown("**Action**")

    for entry in ledger:
        cols = st.columns(widths)
        cols[0].write(tenant_names.get(entry["tenant_id"], entry["tenant_id"]))
        cols[1].write(entry["month"])
        cols[2].write(format_inr(entry["rent_amount"]))
        cols[3].write(format_inr(entry["paid_amount"]))
        cols[4].write(format_inr(entry["balance"]))
        with cols[5]:
            status_badge(entry["payment_status"], PAYMENT_STATUS_TONE.get(entry["payment_status"], "neutral"))

        if can_write and entry["payment_status"] != "PAID":
            with cols[6]:
                with st.popover("Record payment"):
                    balance = float(entry["balance"])
                    amount = st.number_input(
                        "Amount", min_value=0.01, max_value=balance, value=balance,
                        step=0.01, key=f"rent_amount_{entry['id']}",
                    )
                    if st.button("Submit", key=f"rent_submit_{entry['id']}"):
                        api_client.record_rent_payment(entry["id"], str(amount))
                        st.success("Payment recorded.")
                        st.rerun()


render()
