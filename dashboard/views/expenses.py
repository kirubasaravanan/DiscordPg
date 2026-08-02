import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api_client
from ui import CATEGORICAL, SEQUENTIAL_BLUE, api_page, format_inr

CATEGORY_CHOICES = ["MAINTENANCE", "UTILITIES", "SALARY", "SUPPLIES", "OTHER"]


@api_page
def render() -> None:
    st.title("Expenses")

    summary = api_client.get_dashboard_summary()["expenses"]
    st.metric("This month", format_inr(summary["this_month"]))

    income_rows = api_client.get_income_report(months=6)["rows"]
    if income_rows:
        st.subheader("Expense trend (6 months)")
        trend_df = pd.DataFrame(income_rows)
        fig = go.Figure()
        fig.add_scatter(
            x=trend_df["month"], y=trend_df["expenses"], mode="lines+markers",
            fill="tozeroy", name="Expenses", line=dict(color=CATEGORICAL[1]),
        )
        fig.update_layout(
            xaxis_title="Month", yaxis_title="₹", showlegend=False, margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, width="stretch")

    with st.expander("Add expense"):
        with st.form("add_expense_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            category = col1.selectbox("Category", CATEGORY_CHOICES)
            amount = col2.number_input("Amount", min_value=0.01, step=0.01)
            col3, col4 = st.columns(2)
            date = col3.date_input("Date")
            vendor = col4.text_input("Vendor (optional)")
            notes = st.text_input("Notes (optional)")
            submitted = st.form_submit_button("Add expense")
        if submitted:
            api_client.create_expense(
                category=category, amount=str(amount), date=str(date),
                vendor=vendor or None, notes=notes or None,
            )
            st.success("Expense added.")
            st.rerun()

    expenses = api_client.list_expenses()["items"]
    if not expenses:
        st.info("No expenses recorded yet.")
        return

    df = pd.DataFrame(expenses)
    df["amount"] = df["amount"].astype(float)

    st.subheader("By category")
    by_category = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount")
    fig2 = go.Figure()
    fig2.add_bar(y=by_category["category"], x=by_category["amount"], orientation="h", marker_color=SEQUENTIAL_BLUE)
    fig2.update_layout(
        xaxis_title="₹", yaxis_title="", height=max(240, 40 * len(by_category)), margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig2, width="stretch")

    st.subheader("Recent expenses")
    recent = df.sort_values("date", ascending=False)[["date", "category", "amount", "vendor", "notes"]].head(20).copy()
    recent["amount"] = recent["amount"].apply(format_inr)
    st.dataframe(
        recent,
        width="stretch",
        hide_index=True,
        column_config={
            "date": "Date", "category": "Category", "amount": "Amount",
            "vendor": "Vendor", "notes": "Notes",
        },
    )


render()
