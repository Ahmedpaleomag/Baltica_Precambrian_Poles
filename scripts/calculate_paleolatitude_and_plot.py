import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
FIG = REPO / "figures" / "paleolatitude"
PAGES = REPO / "pages"

MASTER_CANDIDATES = [
    DATA / "Baltica_poles.csv",
    DATA / "Baltica_poles.xlsx",
    REPO / "Baltica_poles.csv",
    REPO / "Baltica_poles.xlsx",
]

REF_LAT = 64.0
REF_LON = 28.0

def find_master_file():
    for p in MASTER_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("Expected data/Baltica_poles.csv or data/Baltica_poles.xlsx")

def read_master(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    for sep in [",", "\t", ";"]:
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
            if len(df.columns) > 3:
                return df
        except Exception:
            pass
    return pd.read_csv(path, encoding="utf-8-sig")

def pick_column(df, candidates, required=True):
    norm = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in norm:
            return norm[key]
    if required:
        raise KeyError(f"Missing column. Tried: {candidates}")
    return None

def to_num(s):
    return pd.to_numeric(s, errors="coerce")

def paleolatitude_from_pole(pole_lat, pole_lon, ref_lat=REF_LAT, ref_lon=REF_LON):
    plat = math.radians(float(pole_lat))
    plon = math.radians(float(pole_lon))
    rlat = math.radians(float(ref_lat))
    rlon = math.radians(float(ref_lon))
    cos_c = (
        math.sin(rlat) * math.sin(plat)
        + math.cos(rlat) * math.cos(plat) * math.cos(plon - rlon)
    )
    cos_c = max(-1.0, min(1.0, cos_c))
    colat = math.degrees(math.acos(cos_c))
    return 90.0 - colat

def predicted_inclination_from_paleolat(paleolat):
    return math.degrees(math.atan(2.0 * math.tan(math.radians(float(paleolat)))))

def predicted_declination_from_pole(pole_lat, pole_lon, ref_lat=REF_LAT, ref_lon=REF_LON):
    plat = math.radians(float(pole_lat))
    plon = math.radians(float(pole_lon))
    rlat = math.radians(float(ref_lat))
    rlon = math.radians(float(ref_lon))
    dlon = plon - rlon
    y = math.sin(dlon) * math.cos(plat)
    x = math.cos(rlat) * math.sin(plat) - math.sin(rlat) * math.cos(plat) * math.cos(dlon)
    return math.degrees(math.atan2(y, x)) % 360.0

def main():
    DATA.mkdir(exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(exist_ok=True)

    master_path = find_master_file()
    df = read_master(master_path)
    df.columns = [str(c).strip() for c in df.columns]

    age_col = pick_column(df, ["Age_Ma", "age", "Age"])
    age_min_col = pick_column(df, ["age_min", "lomagage", "Age_min", "Age_min_Ma"], required=False)
    age_max_col = pick_column(df, ["age_max", "himagage", "Age_max", "Age_max_Ma"], required=False)
    rating_col = pick_column(df, ["Rating", "grade", "Grade"], required=False)
    pole_lon_col = pick_column(df, ["P_LONG", "Pole_lon", "Plon", "P_lon"])
    pole_lat_col = pick_column(df, ["P_LAT", "Pole_lat", "Plat", "P_lat"])
    a95_col = pick_column(df, ["A95", "A95_deg", "alpha95"], required=False)

    out = df.copy()
    out["Age_Ma"] = to_num(out[age_col])
    out["Age_min_Ma"] = to_num(out[age_min_col]) if age_min_col else np.nan
    out["Age_max_Ma"] = to_num(out[age_max_col]) if age_max_col else np.nan
    out["Pole_lon"] = to_num(out[pole_lon_col])
    out["Pole_lat"] = to_num(out[pole_lat_col])
    out["A95_deg"] = to_num(out[a95_col]) if a95_col else np.nan
    out["Rating"] = out[rating_col].astype(str).str.strip() if rating_col else ""

    out["Age_err_minus_Ma"] = (out["Age_Ma"] - out["Age_min_Ma"]).abs()
    out["Age_err_plus_Ma"] = (out["Age_max_Ma"] - out["Age_Ma"]).abs()
    out["Age_range_flag"] = np.where(
        out["Age_min_Ma"].isna() | out["Age_max_Ma"].isna(),
        "missing age range",
        np.where(
            (out["Age_Ma"] >= np.minimum(out["Age_min_Ma"], out["Age_max_Ma"]))
            & (out["Age_Ma"] <= np.maximum(out["Age_min_Ma"], out["Age_max_Ma"])),
            "ok",
            "check age range",
        ),
    )

    paleolats, decs, incs = [], [], []
    for _, row in out.iterrows():
        if pd.isna(row["Pole_lat"]) or pd.isna(row["Pole_lon"]):
            paleolats.append(np.nan); decs.append(np.nan); incs.append(np.nan)
            continue
        plat = paleolatitude_from_pole(row["Pole_lat"], row["Pole_lon"])
        paleolats.append(plat)
        incs.append(predicted_inclination_from_paleolat(plat))
        decs.append(predicted_declination_from_pole(row["Pole_lat"], row["Pole_lon"]))

    out["Ref_lat"] = REF_LAT
    out["Ref_lon"] = REF_LON
    out["Paleolatitude_64N_28E_deg"] = paleolats
    out["Pred_dec_at_ref_deg"] = decs
    out["Pred_inc_at_ref_deg"] = incs

    out.to_csv(DATA / "Baltica_paleolatitudes_64N_28E.csv", index=False, encoding="utf-8-sig")
    out.to_excel(DATA / "Baltica_paleolatitudes_64N_28E.xlsx", index=False)

    plot_df = out.dropna(subset=["Age_Ma", "Paleolatitude_64N_28E_deg"]).copy()
    plot_df = plot_df.sort_values("Age_Ma", ascending=False)

    fig, ax = plt.subplots(figsize=(12, 7))
    for rating, sub in plot_df.groupby("Rating", dropna=False):
        label = rating if str(rating).strip() else "unrated"
        ax.errorbar(
            sub["Age_Ma"], sub["Paleolatitude_64N_28E_deg"],
            xerr=[sub["Age_err_minus_Ma"], sub["Age_err_plus_Ma"]],
            yerr=sub["A95_deg"], fmt="o", capsize=3, label=label,
        )
    ax.set_xlabel("Age (Ma)")
    ax.set_ylabel("Paleolatitude at 64N, 28E (deg)")
    ax.set_title("Baltica paleolatitude through time")
    ax.grid(True, alpha=0.35)
    ax.invert_xaxis()
    ax.legend(title="Rating")
    fig.tight_layout()
    fig.savefig(FIG / "Baltica_paleolatitude_all_grades.png", dpi=300)
    plt.close(fig)

    ab = plot_df[plot_df["Rating"].isin(["A", "B"])].copy()
    fig, ax = plt.subplots(figsize=(12, 7))
    for rating, sub in ab.groupby("Rating", dropna=False):
        ax.errorbar(
            sub["Age_Ma"], sub["Paleolatitude_64N_28E_deg"],
            xerr=[sub["Age_err_minus_Ma"], sub["Age_err_plus_Ma"]],
            yerr=sub["A95_deg"], fmt="o", capsize=3, label=rating,
        )
    ax.set_xlabel("Age (Ma)")
    ax.set_ylabel("Paleolatitude at 64N, 28E (deg)")
    ax.set_title("Baltica paleolatitude through time: A- and B-grade poles")
    ax.grid(True, alpha=0.35)
    ax.invert_xaxis()
    ax.legend(title="Rating")
    fig.tight_layout()
    fig.savefig(FIG / "Baltica_paleolatitude_AB_only.png", dpi=300)
    plt.close(fig)

    print("Generated paleolatitude outputs.")

if __name__ == "__main__":
    main()
