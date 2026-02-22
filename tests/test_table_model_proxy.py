from PyQt6.QtCore import QCoreApplication

from xpath_config import XPathItem
from xpath_filter_proxy import XPathFilterProxyModel
from xpath_table_model import XPathItemTableModel


def _ensure_qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _build_items():
    a = XPathItem(name="login_btn", xpath="//button[@id='login']", category="login", description="로그인 버튼")
    a.tags = ["auth", "primary"]
    a.is_favorite = True

    b = XPathItem(name="seat_map", xpath="//div[@id='seat']", category="seat", description="좌석 맵")
    b.tags = ["seat"]
    b.is_favorite = False

    c = XPathItem(name="login_input", xpath="//input[@name='id']", category="login", description="아이디 입력")
    c.tags = ["auth"]
    c.is_favorite = False
    return [a, b, c]


def test_proxy_filters_and_item_mapping():
    _ensure_qt_app()
    model = XPathItemTableModel(_build_items())
    proxy = XPathFilterProxyModel()
    proxy.setSourceModel(model)

    assert model.rowCount() == 3
    assert proxy.rowCount() == 3

    proxy.set_category_filter("login", "전체")
    assert proxy.rowCount() == 2
    assert {proxy.get_item(0).name, proxy.get_item(1).name} == {"login_btn", "login_input"}

    proxy.set_search_text("아이디")
    assert proxy.rowCount() == 1
    assert proxy.get_item(0).name == "login_input"

    proxy.set_search_text("")
    proxy.set_favorites_only(True)
    assert proxy.rowCount() == 1
    assert proxy.get_item(0).name == "login_btn"

    proxy.set_favorites_only(False)
    proxy.set_tag_filter("seat", "모든 태그")
    assert proxy.rowCount() == 0

    proxy.set_category_filter("전체", "전체")
    assert proxy.rowCount() == 1
    assert proxy.get_item(0).name == "seat_map"

