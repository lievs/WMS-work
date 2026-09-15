from datetime import datetime

from openpyxl import Workbook

from wms.extensions import db
from wms.models import Box, BoxItem, MovementDocument, MovementLine, Nomenclature, Warehouse
from wms.utils.google_sheets import (
    _fact_ranges_for_sheet,
    build_wms_movement_rows,
    distribution_sheet_titles,
)


def test_distribution_sheet_titles_ignores_dates_and_non_distribution_sheets():
    titles = distribution_sheet_titles(
        [
            "Распределение FBO ВБ от 12.09",
            "Распределение ОЗОН ФБС от 27.08",
            " ВБ ФБС от 27.08",
            "Приоритет",
        ]
    )
    assert titles == [
        "Распределение FBO ВБ от 12.09",
        "Распределение ОЗОН ФБС от 27.08",
    ]


def test_wms_rows_separate_in_transit_and_received(db):
    sender = Warehouse(code="SYNC-FROM", name="Основной")
    target = Warehouse(
        code="SYNC-TO", name="ОЗОН: Москва", marketplace="ozon", marketplace_city="Москва"
    )
    item = Nomenclature(sku="ART-1", barcode="4600000000001", name="Товар", unit="шт")
    db.session.add_all([sender, target, item])
    db.session.commit()

    for number, received in (("MOVE-TRANSIT", False), ("MOVE-RECEIVED", True)):
        box = Box(box_number=f"BOX-{number}", warehouse_id=target.id, status="open")
        document = MovementDocument(
            number=number,
            from_warehouse_id=sender.id,
            to_warehouse_id=target.id,
            status="completed",
            received_at=datetime.utcnow() if received else None,
        )
        db.session.add_all([box, document])
        db.session.flush()
        db.session.add_all(
            [
                BoxItem(box_id=box.id, nomenclature_id=item.id, qty=5),
                MovementLine(document_id=document.id, box_id=box.id, from_warehouse_id=sender.id),
            ]
        )
    db.session.commit()

    rows = build_wms_movement_rows()
    assert len(rows) == 1
    assert rows[0][6:] == [5.0, 5.0, 10.0]


def test_fact_ranges_target_only_shipment_fact_column():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Распределение ВБ"
    sheet.append(["Артикул", "Баркод", "Москва", "отгружено"])
    sheet.append(["A1", "111", 10, 0])
    sheet.append(["ИТОГО", None, 10, "=SUM(D2:D2)"])

    ranges = _fact_ranges_for_sheet(sheet, "wb", {("wb", "москва", "111"): 7})

    assert ranges == [{"range": "'Распределение ВБ'!D2:D3", "values": [[7], [None]]}]
