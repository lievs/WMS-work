"""Ручная отметка "заявка на МП создана" в списке перемещений — синяя
галочка, независимая и от автоматической выгрузки в 1С, и от отметки
бухгалтера "внесено в 1С" (тот же принцип, что и toggle_accounting, но
отдельное поле — см. MovementDocument.marketplace_request_created_at)."""

from wms.extensions import db
from wms.models import MovementDocument, Warehouse


def _make_document():
    wh1 = Warehouse(code="WH-MP1", name="Склад-отправитель")
    wh2 = Warehouse(code="WH-MP2", name="Склад назначения")
    db.session.add_all([wh1, wh2])
    db.session.commit()
    doc = MovementDocument(number="PER-MP-0001", from_warehouse_id=wh1.id, to_warehouse_id=wh2.id)
    db.session.add(doc)
    db.session.commit()
    return doc


def test_list_shows_unchecked_by_default(db, client_logged_in):
    doc = _make_document()

    resp = client_logged_in.get("/movement/")
    html = resp.get_data(as_text=True)
    idx = html.find(doc.number)

    assert "☐" in html[idx : idx + 1200]


def test_toggle_sets_and_clears_timestamp(db, client_logged_in):
    doc = _make_document()

    client_logged_in.post(f"/movement/{doc.id}/toggle-marketplace-request")
    assert doc.marketplace_request_created_at is not None

    resp = client_logged_in.get("/movement/")
    html = resp.get_data(as_text=True)
    idx = html.find(doc.number)
    assert "✔" in html[idx : idx + 1200]

    client_logged_in.post(f"/movement/{doc.id}/toggle-marketplace-request")
    assert doc.marketplace_request_created_at is None


def test_toggle_is_independent_from_accounting_flag(db, client_logged_in):
    doc = _make_document()

    client_logged_in.post(f"/movement/{doc.id}/toggle-marketplace-request")

    assert doc.marketplace_request_created_at is not None
    assert doc.accounting_entered_at is None
