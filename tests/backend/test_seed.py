from app.database.seed import seed
from app.models import Building, PaymentStatus, RentLedger, Tenant, User


def test_seed_populates_expected_data(db_session):
    seed(db=db_session)

    assert db_session.query(Building).count() == 1
    assert db_session.query(Tenant).count() == 6
    assert db_session.query(User).count() == 4

    statuses = {row.payment_status for row in db_session.query(RentLedger).all()}
    assert statuses == {
        PaymentStatus.PAID,
        PaymentStatus.PARTIAL,
        PaymentStatus.PENDING,
        PaymentStatus.OVERDUE,
    }


def test_seed_is_a_no_op_if_already_seeded(db_session):
    seed(db=db_session)
    first_count = db_session.query(Tenant).count()

    seed(db=db_session)  # should detect the existing Building and skip
    second_count = db_session.query(Tenant).count()

    assert first_count == second_count == 6
