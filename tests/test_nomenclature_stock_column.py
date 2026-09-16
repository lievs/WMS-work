"""В списке номенклатуры колонка "Норма, мин" убрана, вместо нее —
"Остаток" (короба + неразмещенный остаток по товару), см.
nomenclature.list_nomenclature / wms/templates/nomenclature/list.html."""

from wms.extensions import db
from wms.models import Box, BoxItem, Nomenclature, UnplacedStock, Warehouse


def _make_warehouse(suffix):
    wh = Warehouse(code=f"WH-STK{suffix}", name="Склад")
    db.session.add(wh)
    db.session.commit()
    return wh


def _make_item(suffix, name="Товар"):
    item = Nomenclature(sku=f"SKU-STK{suffix}", barcode=f"77704000{suffix}", name=name, unit="шт")
    db.session.add(item)
    db.session.commit()
    return item


def test_norm_column_removed_from_list(db, client_logged_in):
    _make_item("1")

    resp = client_logged_in.get("/nomenclature/")

    html = resp.get_data(as_text=True)
    assert "Норма, мин" not in html
    assert "Остаток" in html


def test_stock_column_sums_boxes_and_unplaced(db, client_logged_in):
    wh = _make_warehouse("2")
    item = _make_item("2", name="Уникальный товар для остатка")

    box = Box(box_number="BOX-STK201", warehouse_id=wh.id, status="open")
    db.session.add(box)
    db.session.commit()
    db.session.add(BoxItem(box_id=box.id, nomenclature_id=item.id, qty=12))
    db.session.add(UnplacedStock(warehouse_id=wh.id, nomenclature_id=item.id, qty=5))
    db.session.commit()

    resp = client_logged_in.get("/nomenclature/")
    html = resp.get_data(as_text=True)
    idx = html.find("Уникальный товар для остатка")

    assert idx != -1
    assert "17 шт" in html[idx : idx + 3000]


def test_stock_shows_zero_for_item_with_no_stock(db, client_logged_in):
    _make_item("3", name="Товар без остатка")

    resp = client_logged_in.get("/nomenclature/")
    html = resp.get_data(as_text=True)
    idx = html.find("Товар без остатка")

    assert idx != -1
    assert "0 шт" in html[idx : idx + 3000]
