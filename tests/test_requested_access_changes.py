from wms.extensions import db
from wms.models import (
    Box,
    BoxItem,
    InventoryDocument,
    MovementDocument,
    Nomenclature,
    PlacementDocument,
    ReceivingDocument,
    User,
    Warehouse,
)


def _user(username):
    user = User(username=username, role="warehouse")
    user.set_password("x")
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def test_staff_sees_only_own_documents_and_cannot_open_foreign(db, client):
    first = _user("documents-first")
    second = _user("documents-second")
    warehouse = Warehouse(code="WH-DOC", name="Основной")
    db.session.add(warehouse)
    db.session.commit()

    definitions = (
        (ReceivingDocument, "/receiving/", "/receiving/{id}"),
        (PlacementDocument, "/placement/", "/placement/{id}"),
        (InventoryDocument, "/inventory/", "/inventory/{id}"),
    )
    created = []
    for index, (model, list_path, detail_path) in enumerate(definitions, start=1):
        own = model(number=f"OWN-{index}", warehouse_id=warehouse.id, created_by_id=first.id)
        foreign = model(number=f"FOREIGN-{index}", warehouse_id=warehouse.id, created_by_id=second.id)
        db.session.add_all([own, foreign])
        created.append((own, foreign, list_path, detail_path))

    own_move = MovementDocument(
        number="OWN-MOVE",
        from_warehouse_id=warehouse.id,
        to_warehouse_id=warehouse.id,
        created_by_id=first.id,
    )
    foreign_move = MovementDocument(
        number="FOREIGN-MOVE",
        from_warehouse_id=warehouse.id,
        to_warehouse_id=warehouse.id,
        created_by_id=second.id,
    )
    db.session.add_all([own_move, foreign_move])
    db.session.commit()
    created.append((own_move, foreign_move, "/movement/", "/movement/{id}"))

    _login(client, first)
    for own, foreign, list_path, detail_path in created:
        html = client.get(list_path).get_data(as_text=True)
        assert own.number in html
        assert foreign.number not in html
        assert client.get(detail_path.format(id=foreign.id)).status_code == 404


def test_invoice_receiving_view_permission_shows_foreign_invoice_read_only(db, client):
    receiver = _user("invoice-receiver")
    author = _user("invoice-author")
    receiver.invoice_receiving_view_allowed = True
    warehouse = Warehouse(code="WH-INVOICE-VIEW", name="Основной")
    db.session.add(warehouse)
    db.session.commit()
    invoice = ReceivingDocument(
        number="INVOICE-SHARED",
        warehouse_id=warehouse.id,
        created_by_id=author.id,
        invoice_file_name="накладная.xlsx",
    )
    manual = ReceivingDocument(
        number="MANUAL-PRIVATE",
        warehouse_id=warehouse.id,
        created_by_id=author.id,
    )
    db.session.add_all([invoice, manual])
    db.session.commit()

    _login(client, receiver)
    html = client.get("/receiving/").get_data(as_text=True)
    assert invoice.number in html
    assert manual.number not in html
    assert client.get(f"/receiving/{invoice.id}").status_code == 200
    assert client.get(f"/receiving/{manual.id}").status_code == 404
    # Право только на просмотр: менять чужую приемку нельзя.
    assert client.post(f"/receiving/{invoice.id}/send-to-recount").status_code == 404


def test_movement_view_permission_shows_foreign_movements_read_only(db, client):
    viewer = _user("movement-viewer")
    author = _user("movement-author")
    viewer.movement_view_allowed = True
    warehouse = Warehouse(code="WH-MOVE-VIEW", name="Основной")
    target = Warehouse(code="WH-MOVE-TARGET", name="Склад №2")
    db.session.add_all([warehouse, target])
    db.session.commit()
    movement = MovementDocument(
        number="MOVE-SHARED",
        from_warehouse_id=warehouse.id,
        to_warehouse_id=target.id,
        created_by_id=author.id,
    )
    db.session.add(movement)
    db.session.commit()

    _login(client, viewer)
    html = client.get("/movement/").get_data(as_text=True)
    assert movement.number in html
    detail = client.get(f"/movement/{movement.id}")
    assert detail.status_code == 200
    assert "Завершить перемещение" not in detail.get_data(as_text=True)
    assert client.post(f"/movement/{movement.id}/complete").status_code == 404


def test_receiving_offers_only_main_and_second_warehouse(db, client_logged_in):
    main = Warehouse(code="WH-001", name="Основной")
    second = Warehouse(code="WH-002", name="Склад №2")
    shosseynaya = Warehouse(code="WH-002-A", name="Склад №2 (Шоссейная 167)")
    hidden = Warehouse(code="WH-003", name="Транзитный")
    db.session.add_all([main, second, shosseynaya, hidden])
    db.session.commit()

    html = client_logged_in.get("/receiving/new").get_data(as_text=True)
    assert "Основной" in html
    assert "Склад №2" in html
    assert "Склад №2 (Шоссейная 167)" in html
    assert "Транзитный" not in html

    client_logged_in.post("/receiving/new", data={"warehouse_id": hidden.id})
    assert ReceivingDocument.query.filter_by(warehouse_id=hidden.id).count() == 0


def test_warehouse_mapping_requires_separate_permission(db, client):
    worker = _user("mapping-worker")
    city = Warehouse(code="CITY-1", name="ОЗОН Казань", marketplace="ozon")
    db.session.add(city)
    db.session.commit()
    _login(client, worker)

    client.post(
        f"/warehouses/{city.id}/fulfillment-1c-name",
        data={"fulfillment_1c_name": "Склад 1С"},
    )
    assert Warehouse.query.get(city.id).fulfillment_1c_name is None

    worker.warehouse_mapping_allowed = True
    db.session.commit()
    client.post(
        f"/warehouses/{city.id}/fulfillment-1c-name",
        data={"fulfillment_1c_name": "Склад 1С"},
    )
    assert Warehouse.query.get(city.id).fulfillment_1c_name == "Склад 1С"


def test_admin_can_grant_warehouse_mapping_permission_in_user_settings(
    db, client_logged_in
):
    worker = _user("mapping-settings-worker")
    html = client_logged_in.get("/users").get_data(as_text=True)
    assert "Разрешить сопоставление складов с 1С" in html

    client_logged_in.post(
        f"/users/{worker.id}/sections",
        data={
            "mode": "full",
            "nomenclature_edit": "on",
            "warehouse_mapping": "on",
            "movement_view": "on",
        },
    )
    assert User.query.get(worker.id).warehouse_mapping_allowed is True
    assert User.query.get(worker.id).movement_view_allowed is True


def test_box_transfer_is_available_in_movements_and_shows_contents(db, client_logged_in):
    warehouse = Warehouse(code="WH-BOX-TRANSFER", name="Основной")
    item = Nomenclature(sku="TRANSFER-SKU", barcode="9900001", name="Товар в коробе", unit="шт")
    source = Box(box_number="BOX-TRANSFER-S", warehouse=warehouse)
    target = Box(box_number="BOX-TRANSFER-T", warehouse=warehouse)
    db.session.add_all([warehouse, item, source, target])
    db.session.commit()
    source_item = BoxItem(box_id=source.id, nomenclature_id=item.id, qty=5)
    db.session.add(source_item)
    db.session.commit()

    html = client_logged_in.get(
        "/movement/box-transfer", query_string={"source_box_number": source.box_number}
    ).get_data(as_text=True)
    assert "Товар в коробе" in html

    client_logged_in.post(
        f"/movement/box-transfer/items/{source_item.id}",
        data={"source_box_id": source.id, "target_box_number": target.box_number, "qty": 2},
    )
    assert BoxItem.query.filter_by(box_id=source.id, nomenclature_id=item.id).first().qty == 3
    assert BoxItem.query.filter_by(box_id=target.id, nomenclature_id=item.id).first().qty == 2
