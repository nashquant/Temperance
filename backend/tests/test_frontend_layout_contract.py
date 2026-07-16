from pathlib import Path


def test_app_layout_keeps_document_scroll_available() -> None:
    source = Path("frontend/src/components/layout/app-layout.tsx").read_text(
        encoding="utf-8"
    )

    assert "h-[100dvh] overflow-hidden bg-background" not in source
    assert "flex h-[100dvh] min-w-0 flex-col overflow-y-auto" not in source
