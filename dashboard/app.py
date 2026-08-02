import streamlit as st

from auth import current_role, render_sidebar_account_info, require_login

st.set_page_config(page_title="PG OS Dashboard", layout="wide")

if not require_login():
    st.stop()

render_sidebar_account_info()

role = current_role()

# Per docs/API.md §3's permission matrix: OWNER/MANAGER/STAFF all have some
# access to Occupancy/Rent/Complaints (STAFF's view is narrower within each
# page — see the views themselves), but Expenses has no STAFF read access at
# all, so it's hidden from navigation entirely rather than shown empty.
pages = [
    st.Page("views/occupancy.py", title="Occupancy", default=True),
    st.Page("views/rent.py", title="Rent"),
    st.Page("views/complaints.py", title="Complaints"),
]
if role in ("OWNER", "MANAGER"):
    pages.append(st.Page("views/expenses.py", title="Expenses"))

navigation = st.navigation(pages)
navigation.run()
