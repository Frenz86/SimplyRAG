"""Genera tutte le varianti di favicon richieste da Open WebUI v0.9.6 a partire da favicon.png.
Centra il logo (anche rettangolare) su un canvas quadrato trasparente, poi esporta:
favicon.ico, favicon-96x96.png, apple-touch-icon.png, favicon.svg (PNG embeddato).
Idempotente: rigenerare quando cambia favicon.png. Vedi LEGGIMI.md."""
import base64
import io
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SRC = HERE / "favicon.png"


def to_square(img: Image.Image) -> Image.Image:
    side = max(img.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    square = to_square(src)

    base = square.resize((512, 512), Image.LANCZOS)

    base.resize((96, 96), Image.LANCZOS).save(HERE / "favicon-96x96.png")
    base.resize((180, 180), Image.LANCZOS).save(HERE / "apple-touch-icon.png")
    base.save(HERE / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'<image href="data:image/png;base64,{b64}" width="512" height="512"/>'
        "</svg>"
    )
    (HERE / "favicon.svg").write_text(svg, encoding="utf-8")

    print("Generati: favicon-96x96.png, apple-touch-icon.png, favicon.ico, favicon.svg")


if __name__ == "__main__":
    main()
