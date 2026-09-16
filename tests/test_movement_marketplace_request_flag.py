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


def test_marketplace_request_number_field_is_not_a_nested_form(db, client_logged_in):
    """Регрессия: поле "№ заявки на МП" раньше рендерилось как отдельный
    <form> внутри строки таблицы, а вся таблица лежит внутри общего
    <form id="waybillsForm"> (нужен для чекбоксов "Объединить"/"Печать").
    Вложенные <form> в HTML недопустимы — браузер молча выбрасывал
    внутренний тег, из-за чего в первой строке список input+кнопка съезжал
    (второй ряд с этим же кодом почему-то сохранял тег — непредсказуемое
    поведение парсера, а не оформление). Поле теперь ссылается на свою
    форму снаружи через form=, без вложенности."""
    doc1 = _make_document()
    wh1 = Warehouse.query.get(doc1.from_warehouse_id)
    wh2 = Warehouse.query.get(doc1.to_warehouse_id)
    doc2 = MovementDocument(number="PER-MP-0002", from_warehouse_id=wh1.id, to_warehouse_id=wh2.id)
    db.session.add(doc2)
    db.session.commit()

    html = client_logged_in.get("/movement/").get_data(as_text=True)

    for doc in (doc1, doc2):
        assert f'form="mpReqForm{doc.id}"' in html
        assert f'<form id="mpReqForm{doc.id}"' in html
        # Само поле не должно открывать свой инлайн-<form> в ячейке —
        # только ссылаться на форму снаружи через form=.
        assert f'<form method="post" action="/movement/{doc.id}/marketplace-request-number"' not in html


def test_set_marketplace_request_number(db, client_logged_in):
    doc = _make_document()

    resp = client_logged_in.post(
        f"/movement/{doc.id}/marketplace-request-number",
        data={"marketplace_request_number": "МП-12345"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert doc.marketplace_request_number == "МП-12345"
    html = resp.get_data(as_text=True)
    idx = html.find(doc.number)
    assert "МП-12345" in html[idx : idx + 1500]


def test_marketplace_request_number_can_be_cleared(db, client_logged_in):
    doc = _make_document()
    doc.marketplace_request_number = "МП-999"
    db.session.commit()

    client_logged_in.post(
        f"/movement/{doc.id}/marketplace-request-number",
        data={"marketplace_request_number": "  "},
    )

    assert doc.marketplace_request_number is None


def test_marketplace_request_number_independent_of_checkbox(db, client_logged_in):
    doc = _make_document()

    client_logged_in.post(
        f"/movement/{doc.id}/marketplace-request-number",
        data={"marketplace_request_number": "МП-777"},
    )

    assert doc.marketplace_request_number == "МП-777"
    assert doc.marketplace_request_created_at is None
