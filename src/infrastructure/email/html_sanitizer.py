import re
from html import escape
from html.parser import HTMLParser

# Mismo whitelist que el editor de texto enriquecido del frontend
# (`sanitizeHtml.ts` / `RichTextEditor.tsx`): negrilla, resaltado y tipo de
# letra. El backend no confía en que el HTML ya llegó sanitizado (la API se
# puede llamar directo, sin pasar por el frontend), así que se vuelve a
# aplicar aquí antes de insertarlo en el correo.
_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "span", "font", "br", "div", "p"}
_ALLOWED_ATTRS = {"style", "color", "face"}
_BLOCK_TAGS = {"div", "p"}

# `contentEditable` deja un `<div><br></div>` (a veces con `&nbsp;` antes)
# al final del mensaje cuando el usuario presiona Enter sin escribir nada
# más. Se recorta esa cola vacía repetidamente hasta el final del string.
_TRAILING_EMPTY_RE = re.compile(
    r"(?:[\s\xa0]|<div>\s*(?:<br\s*/>)?\s*</div>|<p>\s*(?:<br\s*/>)?\s*</p>|<br\s*/>)+$"
)


class _MessageHtmlParser(HTMLParser):
    """
    Sanitiza el HTML de `mensaje` y, en el mismo recorrido, arma el texto
    plano equivalente (para el `text/plain` de respaldo del correo).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._html: list[str] = []
        self._text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in _ALLOWED_TAGS:
            return

        attr_str = "".join(
            f' {name}="{escape(value, quote=True)}"'
            for name, value in attrs
            if name in _ALLOWED_ATTRS and value
        )
        self._html.append(
            f"<{tag}{attr_str} />" if tag == "br" else f"<{tag}{attr_str}>"
        )

        if tag == "br" or tag in _BLOCK_TAGS:
            self._text.append("\n")

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(
        self,
        tag: str
    ) -> None:
        if tag in _ALLOWED_TAGS and tag != "br":
            self._html.append(f"</{tag}>")

    def handle_data(
        self,
        data: str
    ) -> None:
        self._html.append(escape(data))
        self._text.append(data)

    def result(self) -> tuple[str, str]:
        html = _TRAILING_EMPTY_RE.sub("", "".join(self._html)).strip()
        text = re.sub(r"[ \t\xa0]+\n", "\n", "".join(self._text)).strip()
        return html, text


def sanitize_message(html: str) -> tuple[str, str]:
    """
    Devuelve `(html_sanitizado, texto_plano)` a partir del `mensaje` (HTML
    enriquecido) de una notificación.
    """
    parser = _MessageHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.result()
