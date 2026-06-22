from pathlib import Path
import html
import re
import sys

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
ASSESS = REPO / "pole_assessments"
WORKBOOK = DATA / "site_level_data_site_comments_added.xlsx"
MATCH = DATA / "pole_sheet_match.csv"

PREFERRED_COLUMNS = [
    "site", "dir_dec", "dir_inc", "dir_n_samples", "dir_k", "dir_alpha95",
    "vgp_lat", "vgp_lon", "authors", "comment"
]


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def read_match_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    for sep in [",", ";", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
            if len(df.columns) >= 2:
                return df
        except Exception:
            pass
    return pd.read_csv(path, encoding="utf-8-sig")


def pick_col(df, candidates):
    cols = {norm(c): c for c in df.columns}
    for c in candidates:
        key = norm(c)
        if key in cols:
            return cols[key]
    return None


def find_matching_html(pole_id, unit, html_files):
    targets = [norm(pole_id), norm(unit)]
    targets = [t for t in targets if t and t != "nan"]

    for t in targets:
        for f in html_files:
            if t and t in norm(f.stem):
                return f

    for f in html_files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        low = norm(txt)
        for t in targets:
            if t and t in low:
                return f
    return None


def clean_dataframe_for_html(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")

    keep = []
    for c in df.columns:
        cs = str(c).strip()
        if not cs:
            continue
        if cs.lower().startswith("unnamed"):
            continue
        keep.append(c)
    df = df[keep]

    rename = {}
    for c in df.columns:
        cn = norm(c)
        if cn in ["dec_ti", "dec", "d", "dir_dec_deg"]:
            rename[c] = "dir_dec"
        elif cn in ["inc_ti", "inc", "i", "dir_inc_deg"]:
            rename[c] = "dir_inc"
        elif cn in ["n", "dir_n", "n_samples"]:
            rename[c] = "dir_n_samples"
        elif cn == "k":
            rename[c] = "dir_k"
        elif cn in ["a95", "alpha95", "dir_a95"]:
            rename[c] = "dir_alpha95"
        elif cn in ["vgp_long", "vgp_lon", "p_long", "plon"]:
            rename[c] = "vgp_lon"
        elif cn in ["vgp_lat", "p_lat", "plat"]:
            rename[c] = "vgp_lat"
        elif cn in ["authors", "author", "reference", "source"]:
            rename[c] = "authors"
        elif cn in ["comment", "comments", "notes"]:
            rename[c] = "comment"
        elif cn in ["site", "site_name", "locality"]:
            rename[c] = "site"
    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated()]

    cols = [c for c in PREFERRED_COLUMNS if c in df.columns]
    cols += [c for c in df.columns if c not in cols]
    return df[cols]


def fmt_value(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float):
        if abs(v - round(v)) < 1e-10:
            return str(int(round(v)))
        return f"{v:.6g}"
    return str(v)


def dataframe_to_html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return '<p><em>No site-level rows currently available for this matched sheet.</em></p>'
    parts = ['<div class="table-wrap">', '<table>', '<thead><tr>']
    for c in df.columns:
        parts.append(f"<th>{html.escape(str(c))}</th>")
    parts.append('</tr></thead>')
    parts.append('<tbody>')
    for _, row in df.iterrows():
        parts.append('<tr>')
        for c in df.columns:
            parts.append(f"<td>{html.escape(fmt_value(row[c]))}</td>")
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return "\n".join(parts)


def build_site_level_card(sheet_name, df):
    table = dataframe_to_html_table(df)
    return f'''<section class="card" id="site-level-data">
  <h2>Site-level data</h2>
  {table}
  <p class="small-note">
    Source workbook: <code>data/site_level_data_site_comments_added.xlsx</code>;
    sheet: <strong>{html.escape(sheet_name)}</strong>.
    This table is regenerated automatically from the workbook.
  </p>
</section>'''


def replace_site_level_card(page_text, new_card):
    pattern_id = re.compile(r'<section[^>]*id=["\']site-level-data["\'][^>]*>.*?</section>', re.I | re.S)
    if pattern_id.search(page_text):
        return pattern_id.sub(new_card, page_text, count=1)

    h2 = re.search(r'<h2>\s*Site-level data\s*</h2>', page_text, flags=re.I)
    if not h2:
        pos = page_text.lower().rfind("</main>")
        if pos != -1:
            return page_text[:pos] + "\n" + new_card + "\n" + page_text[pos:]
        return page_text + "\n" + new_card

    start = page_text.rfind("<section", 0, h2.start())
    if start == -1:
        start = h2.start()
    end = page_text.find("</section>", h2.end())
    if end == -1:
        next_h2 = page_text.find("<h2>", h2.end())
        end = next_h2 if next_h2 != -1 else h2.end()
        return page_text[:start] + new_card + page_text[end:]
    end += len("</section>")
    return page_text[:start] + new_card + page_text[end:]


def main():
    if not WORKBOOK.exists():
        print(f"Missing workbook: {WORKBOOK}")
        sys.exit(1)
    if not ASSESS.exists():
        print(f"Missing pole_assessments folder: {ASSESS}")
        sys.exit(1)

    match = read_match_table(MATCH)
    match.columns = [str(c).strip() for c in match.columns]
    pole_col = pick_col(match, ["pole_id", "Pole ID", "id"])
    unit_col = pick_col(match, ["unit", "rockname", "ROCKNAME", "name"])
    sheet_col = pick_col(match, ["sheet_name", "sheet", "excel_sheet"])
    if sheet_col is None:
        raise KeyError("pole_sheet_match.csv must contain a sheet_name column.")

    xl = pd.ExcelFile(WORKBOOK)
    sheet_lookup = {norm(s): s for s in xl.sheet_names}
    html_files = list(ASSESS.glob("*.html"))
    updated = 0
    skipped = 0

    for _, row in match.iterrows():
        sheet_requested = row.get(sheet_col, "")
        if pd.isna(sheet_requested) or str(sheet_requested).strip() == "":
            skipped += 1
            continue
        sheet_key = norm(sheet_requested)
        if sheet_key not in sheet_lookup:
            print(f"Sheet not found in workbook, skipping: {sheet_requested}")
            skipped += 1
            continue
        sheet_name = sheet_lookup[sheet_key]
        pole_id = row.get(pole_col, "") if pole_col else ""
        unit = row.get(unit_col, "") if unit_col else sheet_name
        page = find_matching_html(pole_id, unit, html_files)
        if page is None:
            print(f"No matching HTML page found for sheet: {sheet_name} / pole_id: {pole_id}")
            skipped += 1
            continue
        df = pd.read_excel(WORKBOOK, sheet_name=sheet_name)
        df = clean_dataframe_for_html(df)
        new_card = build_site_level_card(sheet_name, df)
        old = page.read_text(encoding="utf-8", errors="ignore")
        new = replace_site_level_card(old, new_card)
        if new != old:
            page.write_text(new, encoding="utf-8")
            print(f"Updated site-level table: {page.name} from sheet {sheet_name}")
            updated += 1
        else:
            print(f"No change: {page.name}")
    print(f"Done. Updated {updated} pages; skipped {skipped} rows.")


if __name__ == "__main__":
    main()
