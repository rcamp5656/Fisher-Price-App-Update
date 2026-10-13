"""Inline src/*.js + style.css into one double-clickable standalone/index.html."""
from pathlib import Path

SRC = Path(__file__).parent / "src"
OUT = Path(__file__).parent / "index.html"
shell = (SRC / "shell.html").read_text(encoding="utf-8")
js = "\n".join((SRC / f).read_text(encoding="utf-8") for f in ("core.js", "geom.js", "audio.js", "store.js", "ui.js"))
js = js.replace("</script>", "<\\/script>")
html = shell.replace("/*__CSS__*/", (SRC / "style.css").read_text(encoding="utf-8")).replace("/*__JS__*/", js)
OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
