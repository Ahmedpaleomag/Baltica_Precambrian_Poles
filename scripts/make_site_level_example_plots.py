from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
FIG = REPO / "figures" / "site_level_examples"

SITE_WORKBOOK_CANDIDATES = [
    DATA / "site_level_data_site_comments_added.xlsx",
    DATA / "site_level_data.xlsx",
    REPO / "site_level_data_site_comments_added.xlsx",
]

# Edit this list to add more example sheets.
EXAMPLES = [
    {
        "pole_id": "smaland_intrusives_c_1777",
        "sheet_name": "Småland intrusives -C",
        "dec_col": "dir_dec",
        "inc_col": "dir_inc",
        "vgp_lat_col": "vgp_lat",
        "vgp_lon_col": "vgp_lon",
    },
    {
        "pole_id": "basu_kukkarauk_formation_c",
        "sheet_name": "Basu-Kukkarauk formation -C",
        "dec_col": "dec_acs",
        "inc_col": "inc_acs",
        "vgp_lat_col": "vgp_lat",
        "vgp_lon_col": "vgp_lon",
    },
]

def slugify(s):
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")

def find_workbook():
    for p in SITE_WORKBOOK_CANDIDATES:
        if p.exists():
            return p
    print("No site-level workbook found; skipping site-level plots.")
    return None

def pick_col(df, candidates):
    norm = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        if c is None:
            continue
        key = str(c).strip().lower()
        if key in norm:
            return norm[key]
    return None

def equal_area_xy(dec_deg, inc_deg):
    dec = np.radians(dec_deg)
    inc = np.radians(np.abs(inc_deg))
    r = np.sqrt(2) * np.sin((np.pi / 2 - inc) / 2)
    x = r * np.sin(dec)
    y = r * np.cos(dec)
    return x, y

def draw_stereonet(ax):
    circle = plt.Circle((0, 0), 1, fill=False, linewidth=1.5)
    ax.add_patch(circle)
    ax.plot([0, 0], [-1, 1], linestyle=":", linewidth=0.8)
    ax.plot([-1, 1], [0, 0], linestyle=":", linewidth=0.8)
    for deg in range(0, 360, 10):
        a = np.radians(deg)
        ax.plot([np.sin(a), 0.97*np.sin(a)], [np.cos(a), 0.97*np.cos(a)], linewidth=0.5)
    ax.text(0, 1.08, "N", ha="center", va="center")
    ax.text(1.08, 0, "E", ha="center", va="center")
    ax.text(0, -1.08, "S", ha="center", va="center")
    ax.text(-1.08, 0, "W", ha="center", va="center")
    ax.set_aspect("equal")
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.axis("off")

def make_stereonet(df, dec_col, inc_col, out_png, title):
    df = df.copy()
    df[dec_col] = pd.to_numeric(df[dec_col], errors="coerce")
    df[inc_col] = pd.to_numeric(df[inc_col], errors="coerce")
    df = df.dropna(subset=[dec_col, inc_col])
    if df.empty:
        print(f"No direction data for {title}")
        return
    down = df[df[inc_col] >= 0]
    up = df[df[inc_col] < 0]
    fig, ax = plt.subplots(figsize=(7, 7))
    draw_stereonet(ax)
    if not down.empty:
        x, y = equal_area_xy(down[dec_col], down[inc_col])
        ax.scatter(x, y, marker="o", label=f"Positive inc. (N={len(down)})")
    if not up.empty:
        x, y = equal_area_xy(up[dec_col], up[inc_col])
        ax.scatter(x, y, marker="o", facecolors="none", edgecolors="black", label=f"Negative inc. (N={len(up)})")
    ax.set_title(title)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=1)
    fig.tight_layout()
    fig.savefig(out_png, dpi=300)
    plt.close(fig)

def make_vgp_plot(df, lat_col, lon_col, out_png, title):
    df = df.copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    if df.empty:
        print(f"No VGP data for {title}")
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(df[lon_col], df[lat_col], marker="o")
    ax.set_xlim(0, 360)
    ax.set_ylim(-90, 90)
    ax.set_xlabel("VGP longitude (deg E)")
    ax.set_ylabel("VGP latitude (deg)")
    ax.set_title(title)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    fig.savefig(out_png, dpi=300)
    plt.close(fig)

def main():
    workbook = find_workbook()
    if workbook is None:
        return
    xl = pd.ExcelFile(workbook)
    existing_sheets = set(xl.sheet_names)
    FIG.mkdir(parents=True, exist_ok=True)
    for ex in EXAMPLES:
        sheet = ex["sheet_name"]
        if sheet not in existing_sheets:
            print(f"Sheet not found, skipping: {sheet}")
            continue
        df = pd.read_excel(workbook, sheet_name=sheet)
        df.columns = [str(c).strip() for c in df.columns]
        dec_col = pick_col(df, [ex.get("dec_col"), "dir_dec", "dec_acs", "Dec", "D"])
        inc_col = pick_col(df, [ex.get("inc_col"), "dir_inc", "inc_acs", "Inc", "I"])
        vgp_lat_col = pick_col(df, [ex.get("vgp_lat_col"), "vgp_lat", "VGP_lat", "Plat", "P_LAT"])
        vgp_lon_col = pick_col(df, [ex.get("vgp_lon_col"), "vgp_lon", "VGP_lon", "Plon", "P_LONG"])
        out_dir = FIG / slugify(ex["pole_id"])
        out_dir.mkdir(parents=True, exist_ok=True)
        if dec_col and inc_col:
            make_stereonet(df, dec_col, inc_col, out_dir / "direction_stereonet.png", f"{sheet}: site directions")
        else:
            print(f"No direction columns found for {sheet}")
        if vgp_lat_col and vgp_lon_col:
            make_vgp_plot(df, vgp_lat_col, vgp_lon_col, out_dir / "vgp_distribution.png", f"{sheet}: VGP distribution")
        else:
            print(f"No VGP columns found for {sheet}")
    print("Finished site-level example plots.")

if __name__ == "__main__":
    main()
