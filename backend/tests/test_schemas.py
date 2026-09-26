import pytest
from pydantic import ValidationError

from backend.app.schemas import CancelIn, EntityIn, InvoiceIn, RateIn


def test_business_fields_are_normalized_at_the_api_boundary():
    entity = EntityIn(code=" demo ", name="  Demo Fuel  ", email="  ", phone="  ")
    assert entity.code == "DEMO"
    assert entity.name == "Demo Fuel"
    assert entity.email is None
    assert entity.phone is None

    rate = RateIn(
        provider_id=1,
        fuel_type=" jet a-1 ",
        rate_per_unit="1.25",
        currency="USD",
        effective_from="2026-01-01",
    )
    assert rate.fuel_type == "JET A-1"

    invoice = InvoiceIn(
        reference=" INV-1 ",
        airline_id=1,
        provider_id=1,
        billing_month="2026-01-01",
        invoice_date="2026-01-15",
        fuel_type=" jet a-1 ",
        quantity="10",
        notes="  ",
    )
    assert invoice.reference == "INV-1"
    assert invoice.fuel_type == "JET A-1"
    assert invoice.notes is None


def test_cancellation_reason_cannot_be_only_whitespace():
    with pytest.raises(ValidationError):
        CancelIn(reason="   ")

    assert CancelIn(reason="  Correction needed  ").reason == "Correction needed"
