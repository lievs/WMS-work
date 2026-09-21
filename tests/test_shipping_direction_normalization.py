from types import SimpleNamespace

from wms.blueprints.shipment_plan import _apply_plan
from wms.models import ShipmentPlanLine, ShippingDirection, Warehouse
from wms.utils.shipping_directions import canonical_city, direction_key


def _parsed(cities):
    return SimpleNamespace(
        sheet_name="Распределение от 20.09",
        cities=cities,
        rows=[
            {"barcode": "460000000001", "article": "A", "size": "M", "city": city, "qty": 1, "fact": 0}
            for city in cities
        ],
    )


def test_city_aliases_and_prefixes_are_canonical():
    assert canonical_city("  ВБ:  спб ") == "Санкт-Петербург"
    assert canonical_city("ОЗОН МОСКВА 2") == "Москва"
    assert direction_key("WB", "ПИТЕР") == direction_key("вб", "Санкт-Петербург")


def test_repeat_import_reuses_directions_and_never_creates_warehouses(db):
    before = Warehouse.query.filter(Warehouse.marketplace.is_(None)).count()
    _apply_plan("wb", _parsed(["МОСКВА", " Москва 1 ", "москва 2", "СПБ", "ПИТЕР"]))
    db.session.commit()

    assert Warehouse.query.filter(Warehouse.marketplace.is_(None)).count() == before
    assert {(d.marketplace, d.city) for d in ShippingDirection.query.all()} == {
        ("wb", "Москва"), ("wb", "Санкт-Петербург")
    }
    assert ShipmentPlanLine.query.count() == 2
    assert sorted(line.planned_qty for line in ShipmentPlanLine.query.all()) == [2, 3]

    _apply_plan("wb", _parsed(["Москва", "Спб"]))
    db.session.commit()
    assert Warehouse.query.filter(Warehouse.marketplace.is_(None)).count() == before
    assert ShippingDirection.query.count() == 2
    assert ShipmentPlanLine.query.count() == 2
