from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_landing_page_smoke() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=30)

    assert not app.exception
    assert any("Crypto Horizon" in title.value for title in app.title) or any(
        "Crypto Horizon" in markdown.value for markdown in app.markdown
    )
    assert len(app.file_uploader) == 1


def test_demo_dashboard_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(root / "app.py"))
    app.session_state["portfolio_bytes"] = (root / "sample_data" / "demo_transactions.csv").read_bytes()
    app.session_state["portfolio_name"] = "demo_transactions.csv"
    app.run(timeout=45)

    assert not app.exception
    assert [metric.label for metric in app.metric[:5]] == [
        "Active positions",
        "Recorded cost basis",
        "Crypto tax-free now",
        "Next unlock",
        "Unmatched sales",
    ]
    assert any("Holding timeline" in markdown.value for markdown in app.markdown)
