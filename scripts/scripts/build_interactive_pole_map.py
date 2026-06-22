from pathlib import Path
import html
import pandas as pd
import folium
from folium.features import RegularPolygonMarker
from branca.colormap import linear

# =========================================================
# Paths
# =========================================================
REPO_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = REPO_DIR / "data" / "Baltica_poles.csv"
OUTPUT_HTML = REPO_DIR / "pages" / "interactive_pole_map.html"

# =========================================================
# Column aliases
# Adjust only here if your CSV uses different column names
# =========================================================
ALIASES = {
    "pole_id": ["pole_id", "id", "slug"],
    "unit": ["unit", "name", "pole_name"],
    "age_ma": ["age_ma", "age", "nominal_age_ma"],
    "grade": ["rating", "grade", "pole_grade"],
    "reference": ["reference", "authors", "citation"],
    "site_lat": ["site_lat", "sample_lat", "present_lat", "lat", "slat"],
    "site_lon": ["site_lon", "sample_lon", "present_lon", "lon", "lng", "slon"],
    "pole_lat": ["pole_lat", "plat", "vgp_lat"],
    "pole_lon": ["pole_lon", "plon", "vgp_lon"],
    "a95": ["a95", "alpha95", "pole_a95"],
    "paleolat": ["paleolat", "paleolatitude"],
}


def normalize(s):
    return str(s).strip().lower()


def find_column(df, choices, required=False):
    lookup = {normalize(c): c for c in df.columns}
    for ch in choices:
        if normalize(ch) in lookup:
            return lookup[normalize(ch)]
    if required:
        raise KeyError(f"Could not find required column from choices: {choices}")
    return None


def safe_text(x):
    if pd.isna(x):
        return "—"
    return html.escape(str(x))


def safe_num(x, ndp=1):
    if pd.isna(x):
        return "—"
    try:
        return f"{float(x):.{ndp}f}"
    except Exception:
        return safe_text(x)


def grade_group_name(grade):
    if pd.isna(grade):
        return "Other / unknown grade"
    g = str(grade).strip().upper()
    if g.startswith("A"):
        return "Grade A poles"
    elif g.startswith("B"):
        return "Grade B poles"
    elif g.startswith("C"):
        return "Grade C poles"
    return "Other / unknown grade"


def add_marker(row, feature_group, cmap):
    age = pd.to_numeric(row.get("age_ma"), errors="coerce")
    color = cmap(age) if pd.notna(age) else "#666666"

    grade = str(row.get("grade", "")).strip().upper()

    # Marker shape:
    # A = circle-like, B = square, C = triangle
    if grade.startswith("A"):
        marker = folium.CircleMarker(
            location=[row["site_lat"], row["site_lon"]],
            radius=7,
            color="black",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
        )
    elif grade.startswith("B"):
        marker = RegularPolygonMarker(
            location=[row["site_lat"], row["site_lon"]],
            number_of_sides=4,
            radius=9,
            rotation=45,
            color="black",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
        )
    else:
        marker = RegularPolygonMarker(
            location=[row["site_lat"], row["site_lon"]],
            number_of_sides=3,
            radius=9,
            rotation=0,
            color="black",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
        )

    pole_link = "—"
    pole_id = row.get("pole_id")
    if pd.notna(pole_id):
        pole_link = f'<a href="../pole_assessments/{pole_id}.html" target="_blank">Open assessment page</a>'

    popup_html = f"""
    <div style="width: 320px; font-size: 14px;">
      <h4 style="margin-bottom: 8px;">{safe_text(row.get("unit"))}</h4>
      <table style="width: 100%; border-collapse: collapse;">
        <tr><td><b>Pole ID</b></td><td>{safe_text(row.get("pole_id"))}</td></tr>
        <tr><td><b>Age (Ma)</b></td><td>{safe_num(row.get("age_ma"), 1)}</td></tr>
        <tr><td><b>Grade</b></td><td>{safe_text(row.get("grade"))}</td></tr>
        <tr><td><b>Sampling site</b></td><td>{safe_num(row.get("site_lat"), 2)}, {safe_num(row.get("site_lon"), 2)}</td></tr>
        <tr><td><b>Pole</b></td><td>{safe_num(row.get("pole_lat"), 2)}, {safe_num(row.get("pole_lon"), 2)}</td></tr>
        <tr><td><b>A95</b></td><td>{safe_num(row.get("a95"), 1)}</td></tr>
        <tr><td><b>Paleolatitude</b></td><td>{safe_num(row.get("paleolat"), 1)}</td></tr>
        <tr><td><b>Reference</b></td><td>{safe_text(row.get("reference"))}</td></tr>
        <tr><td><b>Assessment</b></td><td>{pole_link}</td></tr>
      </table>
    </div>
    """

    marker.add_child(folium.Popup(popup_html, max_width=380))
    marker.add_to(feature_group)


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)

    # Resolve columns
    colmap = {}
    for std_name, choices in ALIASES.items():
        required = std_name in ["pole_id", "unit", "age_ma", "grade", "site_lat", "site_lon"]
        found = find_column(df, choices, required=required)
        if found:
            colmap[found] = std_name

    df = df.rename(columns=colmap)

    # Numeric columns
    for c in ["age_ma", "site_lat", "site_lon", "pole_lat", "pole_lon", "a95", "paleolat"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Keep rows with sampling coordinates
    df = df.dropna(subset=["site_lat", "site_lon"]).copy()

    if df.empty:
        raise ValueError("No rows with valid site_lat and site_lon were found in Baltica_poles.csv")

    # Map center
    center_lat = df["site_lat"].mean()
    center_lon = df["site_lon"].mean()

    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=3,
        tiles="CartoDB positron",
        control_scale=True
    )

    # Title block
    title_html = """
    <div style="
        position: fixed;
        top: 10px;
        left: 60px;
        z-index: 9999;
        background-color: white;
        padding: 10px 14px;
        border: 2px solid #444;
        border-radius: 6px;
        font-size: 18px;
        font-weight: bold;
        ">
        Baltica Precambrian Poles – Interactive pole map
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # Colormap by age
    age_min = float(df["age_ma"].min())
    age_max = float(df["age_ma"].max())
    cmap = linear.Viridis_09.scale(age_min, age_max)
    cmap.caption = "Nominal age (Ma)"
    cmap.add_to(m)

    # Feature groups by grade
    groups = {
        "Grade A poles": folium.FeatureGroup(name="Grade A poles", show=True),
        "Grade B poles": folium.FeatureGroup(name="Grade B poles", show=True),
        "Grade C poles": folium.FeatureGroup(name="Grade C poles", show=True),
        "Other / unknown grade": folium.FeatureGroup(name="Other / unknown grade", show=True),
    }

    for _, row in df.iterrows():
        gname = grade_group_name(row.get("grade"))
        add_marker(row, groups[gname], cmap)

    for grp in groups.values():
        grp.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(OUTPUT_HTML))

    print(f"Interactive map written to: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
