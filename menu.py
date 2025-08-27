import pandas as pd
import numpy as np

menu = pd.read_excel('/Users/calvi/Downloads/ms_annual_data_2022.xlsx')
KEEP_COLS = [
    "menu_item_id",
    "food_category",
    "restaurant",
    "item_name",
    "item_description",
    "calories",
    "total_fat",
    "saturated_fat",
    "trans_fat",
    "cholesterol",
    "sodium",
    "carbohydrates",
    "dietary_fiber",
    "sugar",
    "protein"
]

cols_present = [c for c in KEEP_COLS if c in menu.columns]
df = menu[cols_present].copy()

text_cols = ["menu_item_id","food_category","restaurant","item_name","item_description"]
for c in text_cols:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip()

num_cols = ["calories","total_fat","saturated_fat","trans_fat","cholesterol","sodium",
            "carbohydrates","dietary_fiber","sugar","protein"]
for c in num_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# drop junk rows
df = df[df["item_name"].notna() & df["restaurant"].notna()]
df = df[(df["calories"].notna()) & (df["calories"] > 0)]

for c in num_cols:
    if c in df.columns:
        df.loc[df[c] < 0, c] = np.nan
# sodium likely mg already; if you spot tiny values like <=10, treat as grams -> mg
mask_sod_grams = df["sodium"].notna() & (df["sodium"] <= 10)
df.loc[mask_sod_grams, "sodium"] = df.loc[mask_sod_grams, "sodium"] * 1000

df["_nnz"] = df[num_cols].notna().sum(axis=1)
df = (df.sort_values("_nnz", ascending=False)
        .drop_duplicates(subset=["restaurant","item_name"], keep="first")
        .drop(columns=["_nnz"]))

df["protein_per_100kcal"] = df["protein"] / (df["calories"] / 100.0)
df["fiber_per_100kcal"]   = df["dietary_fiber"] / (df["calories"] / 100.0)
sat100 = df["saturated_fat"] / (df["calories"] / 100.0)
sug100 = df["sugar"] / (df["calories"] / 100.0)
sod100 = (df["sodium"] / (df["calories"] / 100.0)) / 10.0

def add_macro_fields(df):
    cal = df["calories"].clip(lower=1)
    df["protein_per_100kcal"] = df["protein"] / (cal/100)
    df["fiber_per_100kcal"]   = df["dietary_fiber"].fillna(0) / (cal/100)
    sat100 = df["saturated_fat"].fillna(0) / (cal/100)
    sug100 = df["sugar"].fillna(0) / (cal/100)
    sod100 = (df["sodium"].fillna(0) / (cal/100)) / 10.0   # sodium scaled down

    def z(s):
        s = s.replace([np.inf, -np.inf], np.nan).fillna(s.median())
        return (s - s.mean()) / (s.std(ddof=0) + 1e-9)

    # positive drivers
    pos = 0.60*z(df["protein_per_100kcal"]) + 0.20*z(df["fiber_per_100kcal"])
    # penalties
    neg = 0.12*z(sat100) + 0.05*z(sug100) + 0.03*z(sod100)

    raw = pos - neg
    # map to 0–100 with a robust min/max (clip to central range first)
    r = raw.clip(raw.quantile(0.02), raw.quantile(0.98))
    df["macro_score"] = ((r - r.min()) / (r.max() - r.min() + 1e-9) * 100).round(1)
    return df

df = add_macro_fields(df)

def filter_cut(x: pd.DataFrame) -> pd.DataFrame:
    return (x[
        (x['calories'].between(250,700,inclusive = 'both')) &
        (x["protein"] >= 25) &
        (x["protein_per_100kcal"] >= 6) &             
        (x["saturated_fat"].fillna(0) <= 10) &
        (x["sugar"].fillna(0) <= 20) &
        (x["sodium"].fillna(0) <= 1200)
    ].copy())

def filter_bulk(x: pd.DataFrame) -> pd.DataFrame:
    return (x[
        (x["calories"].between(500, 1200, inclusive="both")) &
        (x["protein"] >= 30) &
        (x["protein_per_100kcal"] >= 4) &
        (x["saturated_fat"].fillna(0) <= 18) &
        (x["sugar"].fillna(0) <= 35) &
        (x["sodium"].fillna(0) <= 1600)
    ].copy())

def sort_for_display(x: pd.DataFrame) -> pd.DataFrame:
    cols = ["menu_item_id","food_category","restaurant","item_name","item_description",
            "calories","protein","total_fat","carbohydrates","dietary_fiber","sugar",
            "saturated_fat","trans_fat","cholesterol","sodium",
            "protein_per_100kcal","fiber_per_100kcal","macro_score"]
    cols = [c for c in cols if c in x.columns]
    return (x.sort_values(["restaurant","macro_score","protein_per_100kcal","calories"],
                          ascending=[True, False, False, True])
              [cols])

cut_df  = sort_for_display(filter_cut(df))
bulk_df = sort_for_display(filter_bulk(df))

top_cut  = cut_df.groupby("restaurant", group_keys=False).apply(lambda g: g.head(10))
top_bulk = bulk_df.groupby("restaurant", group_keys=False).apply(lambda g: g.head(10))

print("Rows in df:", len(df))
print("Rows passing CUT:", len(cut_df), "| BULK:", len(bulk_df))
print("\nCUT sample:\n", top_cut.head(12).to_string(index=False))
print("\nBULK sample:\n", top_bulk.head(12).to_string(index=False))

web_df = df.rename(columns={
    "restaurant": "chain",
    "item_name": "name",
    "carbohydrates": "carbs_g",
    "total_fat": "fat_g",
    "dietary_fiber": "fiber_g",
    "sugar": "sugar_g",
    "saturated_fat": "satfat_g",
    "protein": "protein_g",
    "sodium": "sodium_mg"
})[[
    "chain","name","food_category","calories","protein_g","carbs_g","fat_g",
    "fiber_g","sugar_g","satfat_g","trans_fat","cholesterol","sodium_mg"
]]

web_df.to_json("data/items_for_web.json", orient="records")
print("Wrote data/items_for_web.json")