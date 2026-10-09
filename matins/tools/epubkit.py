"""Write an EPUB 3 package (with an EPUB 2 NCX for older readers).

write_epub(path, book_id=..., title=..., files=[(href, xhtml)], spine=[href],
           nav=[(label, "text/href", children)], css=..., ...)

Pages live under OEBPS/text/. Pass `modified` (an ISO timestamp) to make the
output byte-for-byte reproducible: zip entry times are then fixed as well.
"""

import datetime
import html
import os
import zipfile


def _esc(s):
    return html.escape(s or "", quote=False)


def write_epub(out_path, *, book_id, title, files, spine, nav, css, description="",
               languages=("la", "en"), creator="Divinum Officium (texts)", landmarks=(), modified=None):
    def nav_ol(items):
        return "<ol>" + "".join(
            f'<li><a href="{h}">{_esc(l)}</a>{nav_ol(c) if c else ""}</li>' for l, h, c in items) + "</ol>"

    marks = "".join(f'<li><a epub:type="{t}" href="{h}">{_esc(l)}</a></li>' for t, h, l in landmarks)
    nav_doc = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
               '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
               '<head><meta charset="utf-8"/><title>Contents</title><link rel="stylesheet" type="text/css" href="style.css"/></head>'
               f'<body><nav epub:type="toc" id="toc" class="toc"><h1>Contents</h1>{nav_ol(nav)}</nav>'
               + (f'<nav epub:type="landmarks" id="landmarks" hidden="hidden"><ol>{marks}</ol></nav>' if marks else "")
               + '</body></html>')

    counter = [0]

    def ncx_points(items):
        out = []
        for l, h, c in items:
            counter[0] += 1
            out.append(f'<navPoint id="np{counter[0]}" playOrder="{counter[0]}"><navLabel><text>{_esc(l)}</text></navLabel>'
                       f'<content src="{h}"/>{ncx_points(c)}</navPoint>')
        return "".join(out)

    ncx_doc = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head>'
               f'<meta name="dtb:uid" content="{book_id}"/><meta name="dtb:depth" content="3"/></head>'
               f'<docTitle><text>{_esc(title)}</text></docTitle><navMap>{ncx_points(nav)}</navMap></ncx>')

    stamp = modified or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>']
    ids = {}
    for i, (href, _) in enumerate(files):
        ids[href] = f"x{i}"
        manifest.append(f'<item id="x{i}" href="text/{href}" media-type="application/xhtml+xml"/>')
    spine_xml = "".join(f'<itemref idref="{ids[h]}"/>' for h in spine)
    langs = "\n".join(f"<dc:language>{l}</dc:language>" for l in languages)
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{book_id}</dc:identifier>
<dc:title>{_esc(title)}</dc:title>
{langs}
<dc:creator>{_esc(creator)}</dc:creator>
<dc:description>{_esc(description)}</dc:description>
<meta property="dcterms:modified">{stamp}</meta>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx">{spine_xml}</spine>
</package>
"""
    container = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')

    def entry(name, compress):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)) if modified else zipfile.ZipInfo(
            name, date_time=datetime.datetime.now().timetuple()[:6])
        info.compress_type = compress
        info.external_attr = 0o644 << 16
        return info

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".part"
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(entry("mimetype", zipfile.ZIP_STORED), "application/epub+zip")
        z.writestr(entry("META-INF/container.xml", zipfile.ZIP_DEFLATED), container)
        z.writestr(entry("OEBPS/content.opf", zipfile.ZIP_DEFLATED), opf)
        z.writestr(entry("OEBPS/nav.xhtml", zipfile.ZIP_DEFLATED), nav_doc)
        z.writestr(entry("OEBPS/toc.ncx", zipfile.ZIP_DEFLATED), ncx_doc)
        z.writestr(entry("OEBPS/style.css", zipfile.ZIP_DEFLATED), css)
        for href, doc in files:
            z.writestr(entry(f"OEBPS/text/{href}", zipfile.ZIP_DEFLATED), doc)
    os.replace(tmp, out_path)
    return len(files)
