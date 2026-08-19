"""Basic tests for cpy-download."""

import cpy_download


def test_version() -> None:
    assert hasattr(cpy_download, "__version__")
    assert isinstance(cpy_download.__version__, str)


def test_import() -> None:
    import cpy_download

    assert cpy_download is not None
