import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api_client
import auth
from ui import CATEGORICAL, TRACK_GRAY, api_page, status_badge

ROOM_STATUS_TONE = {"AVAILABLE": "good", "FULL": "neutral", "MAINTENANCE": "warning", "INACTIVE": "neutral"}


@api_page
def render() -> None:
    st.title("Occupancy")

    summary = api_client.get_dashboard_summary()["occupancy"]
    total, occupied, vacant = summary["total_beds"], summary["occupied_beds"], summary["vacant_beds"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total beds", total)
    col2.metric("Occupied", occupied)
    col3.metric("Vacant", vacant)

    st.progress(occupied / total if total else 0, text=f"{(occupied / total if total else 0):.0%} occupied")

    role = auth.current_role()
    if role not in ("OWNER", "MANAGER"):
        st.caption("Per-room detail is visible to OWNER and MANAGER only.")
        return

    rows = api_client.get_occupancy_report()["rows"]
    if not rows:
        st.info("No rooms yet.")
        return

    df = pd.DataFrame(rows)
    df["vacant_beds"] = df["capacity"] - df["occupied_beds"]
    df = df.sort_values("room_number")

    st.subheader("By room")
    fig = go.Figure()
    fig.add_bar(y=df["room_number"], x=df["occupied_beds"], name="Occupied", orientation="h", marker_color=CATEGORICAL[0])
    fig.add_bar(y=df["room_number"], x=df["vacant_beds"], name="Vacant", orientation="h", marker_color=TRACK_GRAY)
    fig.update_layout(
        barmode="stack",
        xaxis_title="Beds",
        yaxis_title="Room",
        yaxis_type="category",
        height=max(320, 32 * len(df)),
        legend_title_text="",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Room status")
    header = st.columns([2, 2, 2])
    header[0].markdown("**Room**")
    header[1].markdown("**Beds**")
    header[2].markdown("**Status**")
    for _, row in df.iterrows():
        c1, c2, c3 = st.columns([2, 2, 2])
        c1.write(row["room_number"])
        c2.write(f"{row['occupied_beds']}/{row['capacity']}")
        with c3:
            status_badge(row["status"], ROOM_STATUS_TONE.get(row["status"], "neutral"))


render()
