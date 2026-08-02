import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api_client
import auth
from ui import CATEGORICAL, COMPLAINT_STATUS_TONE, PRIORITY_TONE, TRACK_GRAY, api_page, status_badge

STATUS_OPTIONS = ["", "OPEN", "IN_PROGRESS", "REOPENED", "RESOLVED", "CLOSED"]
STATUS_CHOICES = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED", "REOPENED"]
PRIORITY_CHOICES = ["LOW", "MEDIUM", "HIGH", "URGENT"]


def _truncate(text: str, limit: int = 70) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


@api_page
def render() -> None:
    st.title("Complaints")

    summary = api_client.get_dashboard_summary()["complaints"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Open", summary["open"])
    col2.metric("In progress", summary["in_progress"])
    col3.metric("Urgent", summary["urgent"])

    role = auth.current_role()

    if role in ("OWNER", "MANAGER"):
        by_category = api_client.get_complaints_report()["by_category"]
        if by_category:
            st.subheader("By category")
            df = pd.DataFrame(by_category)
            df["resolved_count"] = df["total_count"] - df["open_count"]
            df = df.sort_values("total_count", ascending=True)

            fig = go.Figure()
            fig.add_bar(y=df["category"], x=df["open_count"], name="Open", orientation="h", marker_color=CATEGORICAL[0])
            fig.add_bar(
                y=df["category"], x=df["resolved_count"], name="Resolved/closed",
                orientation="h", marker_color=TRACK_GRAY,
            )
            fig.update_layout(
                barmode="stack", xaxis_title="Complaints", yaxis_title="",
                height=max(280, 40 * len(df)), legend_title_text="", margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, width="stretch")

    st.subheader("Queue")
    status_filter = st.selectbox("Filter by status", STATUS_OPTIONS, format_func=lambda s: s or "All")
    complaints = api_client.list_complaints(status=status_filter or None)["items"]
    if not complaints:
        st.info("No complaints match this filter.")
        return

    tenant_names = {t["id"]: t["name"] for t in api_client.list_tenants()["items"]}
    room_numbers = {r["id"]: r["room_number"] for r in api_client.list_rooms()["items"]}

    widths = [1.5, 0.8, 1.1, 2.4, 1.4, 1.7, 1.6]
    header = st.columns(widths)
    for col, label in zip(
        header, ["**Tenant**", "**Room**", "**Category**", "**Description**", "**Priority**", "**Status**", "**Action**"]
    ):
        col.markdown(label)

    for c in complaints:
        cols = st.columns(widths)
        cols[0].write(tenant_names.get(c["tenant_id"], c["tenant_id"]))
        cols[1].write(room_numbers.get(c["room_id"], "—"))
        cols[2].write(c["category"].title())
        cols[3].write(_truncate(c["description"]))
        with cols[4]:
            status_badge(c["priority"], PRIORITY_TONE.get(c["priority"], "neutral"))
        with cols[5]:
            status_badge(c["status"], COMPLAINT_STATUS_TONE.get(c["status"], "neutral"))
        with cols[6]:
            with st.popover("Update"):
                new_status = st.selectbox(
                    "Status", STATUS_CHOICES, index=STATUS_CHOICES.index(c["status"]), key=f"status_{c['id']}"
                )
                new_priority = st.selectbox(
                    "Priority", PRIORITY_CHOICES, index=PRIORITY_CHOICES.index(c["priority"]), key=f"priority_{c['id']}"
                )
                if st.button("Save", key=f"save_{c['id']}"):
                    api_client.update_complaint(c["id"], status=new_status, priority=new_priority)
                    st.success("Complaint updated.")
                    st.rerun()


render()
