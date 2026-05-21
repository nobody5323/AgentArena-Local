from pathlib import Path


def test_web_gui_files_exist() -> None:
    root = Path("web")

    assert (root / "package.json").exists()
    assert (root / "index.html").exists()
    assert (root / "src" / "main.jsx").exists()
    assert (root / "src" / "styles.css").exists()


def test_web_gui_uses_lightswind() -> None:
    main = Path("web/src/main.jsx").read_text(encoding="utf-8")
    package = Path("web/package.json").read_text(encoding="utf-8")

    assert "vendor/lightswind.css" in main
    assert '"lightswind"' in package
