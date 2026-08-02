"""Occupancy view — role gating per docs/API.md §3: OWNER/MANAGER see
per-room detail, STAFF sees only the building-wide KPIs.
"""

from conftest import api_get


def test_owner_sees_kpis_matching_live_data(owner_at, owner_token):
    owner_at.switch_page("views/occupancy.py")
    owner_at.run()
    assert not owner_at.exception

    truth = api_get(owner_token, "/dashboard")["occupancy"]
    values = {m.label: m.value for m in owner_at.metric}
    assert values["Total beds"] == str(truth["total_beds"])
    assert values["Occupied"] == str(truth["occupied_beds"])
    assert values["Vacant"] == str(truth["vacant_beds"])


def test_owner_sees_per_room_detail(owner_at):
    owner_at.switch_page("views/occupancy.py")
    owner_at.run()

    assert not owner_at.exception
    assert "By room" in [s.value for s in owner_at.subheader]
    assert "Room status" in [s.value for s in owner_at.subheader]


def test_manager_sees_per_room_detail(manager_at):
    manager_at.switch_page("views/occupancy.py")
    manager_at.run()

    assert not manager_at.exception
    assert "By room" in [s.value for s in manager_at.subheader]


def test_staff_sees_kpis_but_not_per_room_detail(staff_at):
    staff_at.switch_page("views/occupancy.py")
    staff_at.run()

    assert not staff_at.exception
    assert len(staff_at.metric) == 3  # Total beds / Occupied / Vacant, no per-room breakdown
    assert "By room" not in [s.value for s in staff_at.subheader]
    captions = [c.value for c in staff_at.caption]
    assert any("OWNER and MANAGER only" in c for c in captions)
