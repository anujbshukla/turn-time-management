from app.schemas import DashboardWhatIfRequest


def test_dashboard_what_if_accepts_global_filter_scope():
    payload = DashboardWhatIfRequest(
        extra_loaders=1,
        extra_forklifts=2,
        pre_stage_products=True,
        facility_id="FAC001",
        customer_id="CUS001",
        carrier_id="CAR001",
        appointment_type="Inbound",
        date_from="2026-08-14",
        date_to="2026-08-15",
    )

    assert payload.facility_id == "FAC001"
    assert payload.customer_id == "CUS001"
    assert payload.carrier_id == "CAR001"
    assert payload.appointment_type == "Inbound"
    assert str(payload.date_from) == "2026-08-14"
    assert str(payload.date_to) == "2026-08-15"
