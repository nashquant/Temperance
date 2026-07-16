from backend.app.main import _merge_compatible


def test_elliptical_activities_are_merge_compatible() -> None:
    assert _merge_compatible("elliptical", "elliptical") is True
