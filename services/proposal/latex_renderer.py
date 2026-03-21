"""LaTeX template rendering for research proposals.

Converts proposal sections and evidence tables into a compilable LaTeX document.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


# LaTeX special characters that must be escaped
_LATEX_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in a string."""
    pattern = re.compile("|".join(re.escape(k) for k in _LATEX_SPECIAL))
    return pattern.sub(lambda m: _LATEX_SPECIAL[m.group()], text)


_DOC_TEMPLATE = r"""\documentclass[12pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{booktabs}}
\usepackage{{hyperref}}
\usepackage{{geometry}}
\geometry{{margin=2.5cm}}

\title{{{title}}}
\author{{{author}}}
\date{{\today}}

\begin{{document}}
\maketitle
\tableofcontents
\newpage

{body}

\end{{document}}
"""

_SECTION_TEMPLATE = r"""\section{{{heading}}}

{content}

"""

_TABLE_TEMPLATE = r"""\begin{{table}}[ht]
\centering
\caption{{{caption}}}
\begin{{tabular}}{{{col_spec}}}
\toprule
{header_row}
\midrule
{data_rows}
\bottomrule
\end{{tabular}}
\end{{table}}

"""

_REFERENCES_TEMPLATE = r"""\begin{{thebibliography}}{{99}}

{entries}

\end{{thebibliography}}
"""

_BIBITEM_TEMPLATE = r"\bibitem{{{key}}} {authors}. \textit{{{title}}}. {venue}, {year}."


def render_proposal(
    title: str,
    sections: List[Dict],
    references: List[Dict],
    evidence_tables: Optional[List[Dict]] = None,
    author: str = "ScholarOS",
) -> str:
    """Render a complete LaTeX document from proposal components.

    Args:
        title: Proposal title
        sections: List of section dicts with 'heading' and 'content'
        references: List of reference dicts with 'paper_id', 'title', 'authors', 'doi'
        evidence_tables: Optional list of table dicts with 'caption', 'headers', 'rows'
        author: Author name for title page

    Returns:
        Complete LaTeX document string
    """
    body_parts = []

    # Render sections
    for sec in sections:
        heading = escape_latex(sec.get("heading", ""))
        content = _markdown_to_latex(sec.get("content", ""))
        body_parts.append(_SECTION_TEMPLATE.format(heading=heading, content=content))

    # Render evidence tables
    if evidence_tables:
        body_parts.append(r"\section{Evidence Tables}" + "\n\n")
        for table in evidence_tables:
            body_parts.append(_render_table(table))

    # Render references
    if references:
        entries = []
        for ref in references:
            key = re.sub(r"[^a-zA-Z0-9]", "", ref.get("paper_id", "ref"))
            authors = escape_latex(", ".join(ref.get("authors", [])) or "Unknown")
            ref_title = escape_latex(ref.get("title", "Untitled"))
            doi = ref.get("doi", "")
            venue = escape_latex(doi if doi else "Unpublished")
            year = str(ref.get("year", ""))
            entries.append(
                _BIBITEM_TEMPLATE.format(
                    key=key, authors=authors, title=ref_title, venue=venue, year=year
                )
            )
        body_parts.append(
            _REFERENCES_TEMPLATE.format(entries="\n\n".join(entries))
        )

    return _DOC_TEMPLATE.format(
        title=escape_latex(title),
        author=escape_latex(author),
        body="\n".join(body_parts),
    )


def _render_table(table: Dict) -> str:
    """Render a single evidence table."""
    caption = escape_latex(table.get("caption", "Evidence Table"))
    headers = table.get("headers", [])
    rows = table.get("rows", [])

    if not headers:
        return ""

    col_spec = "l" * len(headers)
    header_row = " & ".join(escape_latex(str(h)) for h in headers) + r" \\"
    data_rows_parts = []
    for row in rows:
        cells = [escape_latex(str(row.get(h, ""))) for h in headers]
        data_rows_parts.append(" & ".join(cells) + r" \\")

    return _TABLE_TEMPLATE.format(
        caption=caption,
        col_spec=col_spec,
        header_row=header_row,
        data_rows="\n".join(data_rows_parts),
    )


def _markdown_to_latex(text: str) -> str:
    """Convert basic Markdown to LaTeX (best-effort)."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)
    # Bullet lists
    lines = text.split("\n")
    result = []
    in_list = False
    for line in lines:
        if line.strip().startswith("- "):
            if not in_list:
                result.append(r"\begin{itemize}")
                in_list = True
            result.append(r"\item " + line.strip()[2:])
        else:
            if in_list:
                result.append(r"\end{itemize}")
                in_list = False
            result.append(line)
    if in_list:
        result.append(r"\end{itemize}")
    return "\n".join(result)
