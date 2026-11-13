"""
SALES ANALYSIS PROJECT  (single script, runs end to end)

What it does:
  1. Creates folders: data/ and output/ (with output/charts/)
  2. Loads data/sales_data.csv  (if missing, generates realistic sample data)
  3. Cleans the data
  4. Calculates KPIs: revenue, profit, margin, growth, top products, etc.
  5. Saves 6 charts (PNG), an Excel report (multi-sheet) and a text summary

Run:  python sales_analysis.py

To use YOUR OWN data: put a CSV at data/sales_data.csv with these columns:
  Order ID, Order Date, Customer, Region, Category, Product,
  Quantity, Unit Price, Discount, Unit Cost
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # saves charts to files; works without a display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# 1. FOLDERS
# ----------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output"
CHART_DIR = OUT_DIR / "charts"
for folder in (DATA_DIR, OUT_DIR, CHART_DIR):
    folder.mkdir(parents=True, exist_ok=True)

CSV_PATH = DATA_DIR / "sales_data.csv"


# ----------------------------------------------------------------------
# 2. SAMPLE DATA GENERATOR (only used if you have no CSV yet)
# ----------------------------------------------------------------------
def generate_sample_data(n_rows: int = 3000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    catalog = {
        "Electronics": {"Laptop": (55000, 40000), "Smartphone": (25000, 18000),
                        "Headphones": (3000, 1800), "Smartwatch": (8000, 5200)},
        "Furniture": {"Office Chair": (7000, 4500), "Desk": (12000, 8000),
                      "Bookshelf": (6000, 3800)},
        "Stationery": {"Notebook": (150, 80), "Pen Pack": (200, 110),
                       "Printer Paper": (450, 300)},
        "Home Appliances": {"Mixer Grinder": (4500, 3000), "Air Fryer": (6500, 4300),
                            "Vacuum Cleaner": (9000, 6000)},
    }
    rows = [(c, p, price, cost) for c, items in catalog.items()
            for p, (price, cost) in items.items()]

    regions = ["North", "South", "East", "West"]
    region_weights = [0.20, 0.35, 0.20, 0.25]
    customers = [f"Customer {i:03d}" for i in range(1, 151)]

    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(
        rng.integers(0, 730, n_rows), unit="D")

    picks = rng.integers(0, len(rows), n_rows)
    df = pd.DataFrame({
        "Order ID": [f"ORD{100000 + i}" for i in range(n_rows)],
        "Order Date": dates,
        "Customer": rng.choice(customers, n_rows),
        "Region": rng.choice(regions, n_rows, p=region_weights),
        "Category": [rows[i][0] for i in picks],
        "Product": [rows[i][1] for i in picks],
        "Quantity": rng.integers(1, 8, n_rows),
        "Unit Price": [rows[i][2] for i in picks],
        "Discount": rng.choice([0, 0.05, 0.10, 0.15, 0.20], n_rows,
                               p=[0.45, 0.2, 0.2, 0.1, 0.05]),
        "Unit Cost": [rows[i][3] for i in picks],
    })

    # Add a little real-world mess so the cleaning step has something to do
    df.loc[rng.choice(n_rows, 15, replace=False), "Region"] = None
    df = pd.concat([df, df.sample(10, random_state=1)])  # duplicate rows
    return df.sort_values("Order Date").reset_index(drop=True)


# ----------------------------------------------------------------------
# 3. LOAD + CLEAN
# ----------------------------------------------------------------------
if not CSV_PATH.exists():
    print("No data found -> generating sample data...")
    generate_sample_data().to_csv(CSV_PATH, index=False)

df = pd.read_csv(CSV_PATH, parse_dates=["Order Date"])
print(f"Loaded {len(df):,} rows")

before = len(df)
df = df.drop_duplicates()
df["Region"] = df["Region"].fillna("Unknown")
df = df.dropna(subset=["Order Date", "Quantity", "Unit Price"])
df = df[(df["Quantity"] > 0) & (df["Unit Price"] > 0)]
print(f"Cleaning removed {before - len(df)} bad/duplicate rows -> {len(df):,} remain")

# ----------------------------------------------------------------------
# 4. FEATURE COLUMNS
# ----------------------------------------------------------------------
df["Revenue"] = df["Quantity"] * df["Unit Price"] * (1 - df["Discount"])
df["Cost"] = df["Quantity"] * df["Unit Cost"]
df["Profit"] = df["Revenue"] - df["Cost"]
df["Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
df["Year"] = df["Order Date"].dt.year
df["Weekday"] = df["Order Date"].dt.day_name()

# ----------------------------------------------------------------------
# 5. ANALYSIS
# ----------------------------------------------------------------------
total_rev = df["Revenue"].sum()
total_profit = df["Profit"].sum()
margin = total_profit / total_rev * 100
orders = df["Order ID"].nunique()
aov = total_rev / orders


def summarize(by):
    t = (df.groupby(by)
           .agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum"),
                Orders=("Order ID", "nunique"), Units=("Quantity", "sum"))
           .sort_values("Revenue", ascending=False))
    t["Margin %"] = (t["Profit"] / t["Revenue"] * 100).round(2)
    return t.round(2)


by_region = summarize("Region")
by_category = summarize("Category")
by_product = summarize("Product")
top_customers = summarize("Customer").head(10)

monthly = (df.groupby("Month")
             .agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum"))
             .round(2))
monthly["MoM Growth %"] = (monthly["Revenue"].pct_change() * 100).round(2)

yearly = df.groupby("Year")["Revenue"].sum()
weekday = (df.groupby("Weekday")["Revenue"].sum()
             .reindex(["Monday", "Tuesday", "Wednesday", "Thursday",
                       "Friday", "Saturday", "Sunday"]))

best_month = monthly["Revenue"].idxmax()
worst_month = monthly["Revenue"].idxmin()

# ----------------------------------------------------------------------
# 6. CHARTS
# ----------------------------------------------------------------------
plt.style.use("seaborn-v0_8-whitegrid")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CHART_DIR / name, dpi=150)
    plt.close(fig)


# 6.1 Monthly revenue & profit
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(monthly.index, monthly["Revenue"], marker="o", label="Revenue")
ax.plot(monthly.index, monthly["Profit"], marker="s", label="Profit")
ax.set_title("Monthly Revenue and Profit")
ax.set_ylabel("Amount")
ax.legend()
save(fig, "1_monthly_trend.png")

# 6.2 Revenue by region
fig, ax = plt.subplots(figsize=(7, 5))
by_region["Revenue"].plot(kind="bar", ax=ax, color="#4C72B0")
ax.set_title("Revenue by Region")
ax.set_ylabel("Revenue")
plt.setp(ax.get_xticklabels(), rotation=0)
save(fig, "2_revenue_by_region.png")

# 6.3 Category share
fig, ax = plt.subplots(figsize=(6, 6))
ax.pie(by_category["Revenue"], labels=by_category.index, autopct="%1.1f%%",
       startangle=90)
ax.set_title("Revenue Share by Category")
save(fig, "3_category_share.png")

# 6.4 Top 10 products
fig, ax = plt.subplots(figsize=(9, 5))
by_product["Revenue"].head(10).sort_values().plot(kind="barh", ax=ax,
                                                  color="#55A868")
ax.set_title("Top 10 Products by Revenue")
ax.set_xlabel("Revenue")
save(fig, "4_top_products.png")

# 6.5 Profit margin by category
fig, ax = plt.subplots(figsize=(7, 5))
by_category["Margin %"].sort_values().plot(kind="barh", ax=ax, color="#C44E52")
ax.set_title("Profit Margin % by Category")
ax.set_xlabel("Margin %")
save(fig, "5_margin_by_category.png")

# 6.6 Sales by weekday
fig, ax = plt.subplots(figsize=(8, 5))
weekday.plot(kind="bar", ax=ax, color="#8172B2")
ax.set_title("Revenue by Weekday")
ax.set_ylabel("Revenue")
plt.setp(ax.get_xticklabels(), rotation=30)
save(fig, "6_weekday_sales.png")

# ----------------------------------------------------------------------
# 7. SAVE EVERYTHING
# ----------------------------------------------------------------------
# 7.1 Cleaned data
df.drop(columns=["Month", "Year", "Weekday"]).to_csv(
    OUT_DIR / "cleaned_sales_data.csv", index=False)

# 7.2 Excel report (needs openpyxl)
with pd.ExcelWriter(OUT_DIR / "sales_report.xlsx") as writer:
    pd.DataFrame({
        "KPI": ["Total Revenue", "Total Profit", "Profit Margin %",
                "Total Orders", "Avg Order Value"],
        "Value": [round(total_rev, 2), round(total_profit, 2), round(margin, 2),
                  orders, round(aov, 2)],
    }).to_excel(writer, sheet_name="KPIs", index=False)
    by_region.to_excel(writer, sheet_name="By Region")
    by_category.to_excel(writer, sheet_name="By Category")
    by_product.to_excel(writer, sheet_name="By Product")
    top_customers.to_excel(writer, sheet_name="Top Customers")
    monthly.to_excel(writer, sheet_name="Monthly Trend")

# 7.3 Text summary
summary = f"""SALES ANALYSIS SUMMARY
======================
Period            : {df['Order Date'].min().date()} to {df['Order Date'].max().date()}
Total Revenue     : {total_rev:,.2f}
Total Profit      : {total_profit:,.2f}
Profit Margin     : {margin:.2f}%
Total Orders      : {orders:,}
Avg Order Value   : {aov:,.2f}

Best Region       : {by_region.index[0]} ({by_region['Revenue'].iloc[0]:,.0f})
Best Category     : {by_category.index[0]} ({by_category['Revenue'].iloc[0]:,.0f})
Best Product      : {by_product.index[0]} ({by_product['Revenue'].iloc[0]:,.0f})
Best Month        : {best_month:%B %Y}
Weakest Month     : {worst_month:%B %Y}
Best Weekday      : {weekday.idxmax()}

Yearly Revenue:
{yearly.round(0).to_string()}

Top 5 Customers:
{top_customers['Revenue'].head(5).to_string()}
"""
(OUT_DIR / "summary.txt").write_text(summary, encoding="utf-8")

print(summary)
print(f"All files saved in: {OUT_DIR}")
