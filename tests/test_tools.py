import socket
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from gaia_agent.config import Settings, safe_error
from gaia_agent.net import validate_public_url
from gaia_agent.tools import Tools, calculator, youtube_id


@pytest.mark.parametrize(
    "expression, expected", [("sum([1,2,3]) / 2", 3), ("round(sqrt(81) + 1.25, 1)", 10.2), ("-2**3", -8)]
)
def test_calculator(expression, expected):
    assert calculator(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').getcwd()",
        "(1).__class__",
        "[0] * 1000000000",
        "10**1000000",
        "True + 1",
        "float('inf')",
    ],
)
def test_calculator_blocks_execution_and_unbounded_work(expression):
    with pytest.raises((ValueError, TypeError)):
        calculator(expression)


def test_xlsx_read_coordinates_and_exact_aggregation(tmp_path):
    path = tmp_path / "sales.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Menu"
    sheet.append(["Item", "Revenue"])
    sheet.append(["Food A", 0.1])
    sheet.append(["Drink", 9.99])
    sheet.append(["Food B", 0.2])
    book.save(path)
    tools = Tools(SimpleNamespace(settings=Settings(token="test")), [path])
    text = tools.read_file(path.name)["text"]
    assert "A2=Food A" in text and "B3=9.99" in text
    assert tools.spreadsheet_sum(path.name, "Menu", "B", [2, 4])["two_decimals"] == "0.30"
    with pytest.raises(ValueError):
        tools.path("../../.env")
    with pytest.raises(ValueError):
        tools.spreadsheet_sum(path.name, "Menu", "B", [2, 2])


def test_formula_without_cache_is_not_silently_zero(tmp_path):
    path = tmp_path / "formula.xlsx"
    book = Workbook()
    book.active["A1"] = "=1+2"
    book.save(path)
    tools = Tools(SimpleNamespace(settings=Settings()), [path])
    assert "=1+2" in tools.read_file(path.name, formulas=True)["text"]
    with pytest.raises(ValueError, match="cached"):
        tools.spreadsheet_sum(path.name, "Sheet", "A", [1])


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://169.254.169.254",
        "http://[::1]",
        "file:///etc/passwd",
        "http://user:pass@example.com",
        "https://example.com:8888",
    ],
)
def test_private_urls_are_blocked(url):
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_dns_name_resolving_private_is_blocked(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))],
    )
    with pytest.raises(ValueError):
        validate_public_url("https://malicious.example")


def test_youtube_url_cannot_inject_another_host():
    assert youtube_id("https://www.youtube.com/watch?v=L1vXCYZAYYM") == "L1vXCYZAYYM"
    with pytest.raises(ValueError):
        youtube_id("https://youtube.com.attacker.test/watch?v=L1vXCYZAYYM")


def test_errors_redact_tokens():
    assert "hf_secret" not in safe_error(ValueError("bad hf_secret"))
    assert "private-token" not in safe_error(ValueError("bad private-token"), "private-token")
