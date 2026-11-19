"""
Database Subsystem Manager for MultiEchelonDSS
Handles SQLite initialization, real supply chain dataset ingestion,
and query interfaces for optimization models and dashboard exports.
Sprague (1980) Compliant Relational Store.
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

# Safe absolute path resolution regardless of execution context or working directory
try:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    CURRENT_DIR = os.path.abspath(os.path.join(os.getcwd(), "database"))

PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR).lower() == "database" else CURRENT_DIR

DB_FILE = os.path.join(CURRENT_DIR, "multiechelon_dss.db")
SCHEMA_FILE = os.path.join(CURRENT_DIR, "schema.sql")

# Dataset CSV path discovery
DATASET_CSV = os.path.join(PROJECT_ROOT, "Dataset", "supply_chain_dataset1.csv")
if not os.path.exists(DATASET_CSV):
    alt_candidates = [
        os.path.join(CURRENT_DIR, "..", "Dataset", "supply_chain_dataset1.csv"),
        os.path.join(os.getcwd(), "Dataset", "supply_chain_dataset1.csv"),
        os.path.join(os.getcwd(), "supply_chain_dataset1.csv"),
    ]
    for cand in alt_candidates:
        if os.path.exists(cand):
            DATASET_CSV = os.path.abspath(cand)
            break


def get_connection(db_path=DB_FILE):
    """Return SQLite connection with Row factory and busy timeout."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path=DB_FILE, schema_path=SCHEMA_FILE):
    """Execute schema script to initialize tables and indices."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        with open(schema_path, "r", encoding="utf-8") as f:
            cursor.executescript(f.read())
        conn.commit()
    finally:
        conn.close()
    print(f"[DB] Initialized schema at: {db_path}")


def ingest_supply_chain_dataset(csv_path=DATASET_CSV, db_path=DB_FILE):
    """
    Ingest real multi-echelon supply chain dataset (91,250 records).
    Populates:
      - echelons: 3 tiers (Supplier, Warehouse/DC, Retail)
      - facilities: Suppliers (SUP_1..10), Warehouses (WH_1..5), Retail zones (REG_West..East)
      - products: 50 SKUs (SKU_1..SKU_50) with empirical unit costs and prices
      - historical_demand: Daily sales records per warehouse and SKU
      - inventory_snapshot: Baseline inventory, safety stock, and reorder points
    """
    if not os.path.exists(csv_path):
        print(f"[DB Warning] Dataset CSV not found at {csv_path}. Falling back to synthetic.")
        seed_master_data_synthetic(db_path)
        generate_synthetic_demand(db_path)
        return

    print(f"[DB] Ingesting real supply chain dataset from: {csv_path}")
    df = pd.read_csv(csv_path)

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()

        # Clear existing data
        cur.execute("DELETE FROM optimization_results")
        cur.execute("DELETE FROM inventory_snapshot")
        cur.execute("DELETE FROM historical_demand")
        cur.execute("DELETE FROM products")
        cur.execute("DELETE FROM facilities")
        cur.execute("DELETE FROM echelons")

        # 1. Populate Echelons
        echelons = [
            (1, "Tier 1: Central Supplier / Plant", 1, 7, 0.40, 450.0, 35.0),
            (2, "Tier 2: Regional Distribution Centers", 2, 3, 0.90, 200.0, 50.0),
            (3, "Tier 3: Retail Outlets", 3, 1, 1.80, 80.0, 85.0),
        ]
        cur.executemany(
            """INSERT INTO echelons (echelon_id, echelon_name, echelon_tier, lead_time_days, 
               holding_cost_per_unit, order_fixed_cost, stockout_penalty_per_unit) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            echelons,
        )

        # 2. Populate Facilities
        facilities = []
        # Tier 1: Suppliers
        suppliers = sorted(df["Supplier_ID"].unique())
        supplier_cities = [
            "Chicago Central", "Detroit Hub", "Atlanta Complex", "Dallas Works", "Seattle Depot",
            "Cleveland Works", "Houston Plant", "Denver Terminal", "Phoenix Facility", "Boston Center"
        ]
        for idx, sup_id in enumerate(suppliers):
            city = supplier_cities[idx % len(supplier_cities)]
            facilities.append((sup_id, f"Supplier Plant {sup_id} ({city})", 1, city, 100000))

        # Tier 2: Warehouses
        warehouses = sorted(df["Warehouse_ID"].unique())
        wh_cities = ["North Regional DC", "South Regional DC", "East Regional DC", "West Regional DC", "Central Regional DC"]
        for idx, wh_id in enumerate(warehouses):
            loc = wh_cities[idx % len(wh_cities)]
            facilities.append((wh_id, f"Distribution Center {wh_id} ({loc})", 2, loc, 35000))

        # Tier 3: Retail Regions
        regions = sorted(df["Region"].unique())
        for reg in regions:
            facilities.append((f"REG_{reg}", f"{reg} Regional Retail Outlets", 3, f"{reg} Zone", 15000))

        cur.executemany(
            """INSERT INTO facilities (facility_id, facility_name, echelon_id, location, max_capacity)
               VALUES (?, ?, ?, ?, ?)""",
            facilities,
        )

        # 3. Populate Products (50 SKUs)
        sku_stats = df.groupby("SKU_ID").agg({
            "Unit_Cost": "mean",
            "Unit_Price": "mean",
        }).reset_index()

        def sku_sort_key(s):
            digits = "".join(ch for ch in str(s) if ch.isdigit())
            return int(digits) if digits else 999999

        sku_stats["sort_key"] = sku_stats["SKU_ID"].apply(sku_sort_key)
        sku_stats = sku_stats.sort_values("sort_key").reset_index(drop=True)

        products = []
        for _, row in sku_stats.iterrows():
            sku_id = row["SKU_ID"]
            cost = round(float(row["Unit_Cost"]), 2)
            price = round(float(row["Unit_Price"]), 2)
            p_name = f"Commercial Product {sku_id} (Cost: ${cost:.2f}, Price: ${price:.2f})"
            products.append((sku_id, p_name, cost, price, 20))

        cur.executemany(
            """INSERT INTO products (product_id, product_name, unit_cost, selling_price, min_order_qty)
               VALUES (?, ?, ?, ?, ?)""",
            products,
        )

        # 4. Ingest Historical Demand (91,250 records)
        demand_records = df[["Date", "Warehouse_ID", "SKU_ID", "Units_Sold"]].values.tolist()
        cur.executemany(
            "INSERT INTO historical_demand (date, facility_id, product_id, demand_qty) VALUES (?, ?, ?, ?)",
            demand_records,
        )

        # 5. Populate Inventory Snapshots (Day 1: 2024-01-01)
        day1_df = df[df["Date"] == "2024-01-01"]
        snapshots = []
        today_str = "2024-01-01"

        for sku_id in sku_stats["SKU_ID"]:
            sku_day1 = day1_df[day1_df["SKU_ID"] == sku_id]
            total_wh_inv = float(sku_day1["Inventory_Level"].sum())

            # Tier 2: Warehouses
            for _, r in sku_day1.iterrows():
                wh_id = r["Warehouse_ID"]
                inv = int(r["Inventory_Level"])
                in_transit = int(r["Order_Quantity"])
                rop = int(r["Reorder_Point"])
                safety = max(10, int(rop * 0.45))
                snapshots.append((today_str, wh_id, sku_id, inv, in_transit, safety, rop))

            # Tier 1: Primary Supplier for this SKU
            primary_sup = sku_day1.iloc[0]["Supplier_ID"] if len(sku_day1) > 0 else "SUP_1"
            sup_inv = max(5000, int(total_wh_inv * 2.5))
            sup_safety = int(sup_inv * 0.2)
            sup_rop = int(sup_inv * 0.4)
            snapshots.append((today_str, primary_sup, sku_id, sup_inv, 1000, sup_safety, sup_rop))

            # Tier 3: Retail Regions
            for reg in regions:
                reg_id = f"REG_{reg}"
                reg_inv = max(50, int(total_wh_inv * 0.05))
                reg_safety = int(reg_inv * 0.3)
                reg_rop = int(reg_inv * 0.6)
                snapshots.append((today_str, reg_id, sku_id, reg_inv, 0, reg_safety, reg_rop))

        cur.executemany(
            """INSERT INTO inventory_snapshot 
               (date, facility_id, product_id, starting_inventory, in_transit_qty, safety_stock, reorder_point)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            snapshots,
        )

        conn.commit()
        print(f"[DB] Ingestion complete: {len(products)} products, {len(facilities)} facilities, "
              f"{len(demand_records)} demand records, {len(snapshots)} inventory snapshots.")
    finally:
        conn.close()


def seed_master_data_synthetic(db_path=DB_FILE):
    """Fallback synthetic master data if dataset CSV is unavailable."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM echelons")
        cur.execute("DELETE FROM facilities")
        cur.execute("DELETE FROM products")

        echelons = [
            (1, "Tier 1: Central Supplier / Plant", 1, 5, 0.40, 450.0, 35.0),
            (2, "Tier 2: Regional Distribution Center", 2, 3, 0.90, 200.0, 50.0),
            (3, "Tier 3: Retail Outlets", 3, 1, 1.80, 80.0, 85.0),
        ]
        cur.executemany(
            """INSERT INTO echelons (echelon_id, echelon_name, echelon_tier, lead_time_days, 
               holding_cost_per_unit, order_fixed_cost, stockout_penalty_per_unit) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            echelons,
        )

        facilities = [
            ("SUP-01", "Global Central Plant", 1, "Chicago Hub", 100000),
            ("RDC-01", "Metro Regional DC", 2, "Dallas DC", 35000),
            ("RET-01", "Retail Store North", 3, "New York Metro", 6000),
            ("RET-02", "Retail Store South", 3, "Houston Metro", 5000),
            ("RET-03", "Retail Store West", 3, "Denver Metro", 4500),
        ]
        cur.executemany(
            """INSERT INTO facilities (facility_id, facility_name, echelon_id, location, max_capacity)
               VALUES (?, ?, ?, ?, ?)""",
            facilities,
        )

        products = [
            ("SKU_1", "High-Velocity Consumer Tech (SKU_1)", 11.56, 16.66, 25),
            ("SKU-100", "High-Velocity Consumer Tech", 45.0, 95.0, 25),
            ("SKU-200", "Industrial Sensor Module", 80.0, 160.0, 15),
            ("SKU-300", "Perishable Eco-Packaging Pack", 12.0, 30.0, 50),
        ]
        cur.executemany(
            """INSERT INTO products (product_id, product_name, unit_cost, selling_price, min_order_qty)
               VALUES (?, ?, ?, ?, ?)""",
            products,
        )
        conn.commit()
    finally:
        conn.close()


def generate_synthetic_demand(db_path=DB_FILE, days=90, seed=42):
    """Fallback synthetic demand generator."""
    random.seed(seed)
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM historical_demand")
        cur.execute("DELETE FROM inventory_snapshot")

        # Query facilities to ensure foreign key compliance
        cur.execute("SELECT facility_id, echelon_id FROM facilities")
        fac_rows = cur.fetchall()
        t3_facs = [r["facility_id"] for r in fac_rows if r["echelon_id"] == 3] or ["RET-01", "RET-02", "RET-03"]
        t2_facs = [r["facility_id"] for r in fac_rows if r["echelon_id"] == 2] or ["RDC-01"]
        t1_facs = [r["facility_id"] for r in fac_rows if r["echelon_id"] == 1] or ["SUP-01"]

        cur.execute("SELECT product_id FROM products")
        prod_rows = cur.fetchall()
        products = [r["product_id"] for r in prod_rows] or ["SKU_1", "SKU-100", "SKU-200", "SKU-300"]

        start_date = datetime(2024, 1, 1)
        records = []

        for day in range(days):
            current_date = (start_date + timedelta(days=day)).strftime("%Y-%m-%d")
            weekly_factor = 1.25 if day % 7 in [4, 5] else 0.95
            for fac in t3_facs:
                for prod in products:
                    base = 45
                    noise = random.gauss(0, base * 0.18)
                    qty = max(5, int(base * weekly_factor + noise))
                    records.append((current_date, fac, prod, qty))

        cur.executemany(
            "INSERT INTO historical_demand (date, facility_id, product_id, demand_qty) VALUES (?, ?, ?, ?)",
            records,
        )

        snapshots = []
        for prod in products:
            snapshots.append(("2024-01-01", t1_facs[0], prod, 8500, 2000, 1500, 3000))
            snapshots.append(("2024-01-01", t2_facs[0], prod, 2200, 600, 500, 1100))
            snapshots.append(("2024-01-01", t3_facs[0], prod, 420, 150, 120, 260))

        cur.executemany(
            """INSERT INTO inventory_snapshot 
               (date, facility_id, product_id, starting_inventory, in_transit_qty, safety_stock, reorder_point)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            snapshots,
        )
        conn.commit()
    finally:
        conn.close()


def seed_master_data(db_path=DB_FILE):
    """Standard seeder: uses real dataset CSV if present, otherwise synthetic fallback."""
    if os.path.exists(DATASET_CSV):
        ingest_supply_chain_dataset(DATASET_CSV, db_path)
    else:
        seed_master_data_synthetic(db_path)
        generate_synthetic_demand(db_path)


def get_available_products(db_path=DB_FILE):
    """Retrieve all available SKUs sorted numerically."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query("SELECT product_id, product_name, unit_cost, selling_price FROM products", conn)
    finally:
        conn.close()

    if len(df) == 0:
        return []

    def sku_sort_key(s):
        digits = "".join(ch for ch in str(s) if ch.isdigit())
        return int(digits) if digits else 999999

    df["sort_key"] = df["product_id"].apply(sku_sort_key)
    df = df.sort_values("sort_key").reset_index(drop=True)
    return df.drop(columns=["sort_key"]).to_dict("records")


def load_dataset_for_optimizer(product_id="SKU_1", horizon_days=30, db_path=DB_FILE):
    """
    Retrieve historical demand summary, current inventory, and cost parameters
    for mathematical multi-echelon optimization.
    Supports both load_dataset_for_optimizer("SKU_1", 30) and load_dataset_for_optimizer(product_id="SKU_1").
    """
    if str(product_id).endswith(".db") or os.path.isabs(str(product_id)):
        actual_db = str(product_id)
        actual_sku = horizon_days if isinstance(horizon_days, str) else "SKU_1"
        actual_horizon = db_path if isinstance(db_path, int) else 30
        db_path = actual_db
        product_id = actual_sku
        horizon_days = actual_horizon

    conn = get_connection(db_path)
    try:
        echelons_df = pd.read_sql_query("SELECT * FROM echelons ORDER BY echelon_tier ASC", conn)
        facilities_df = pd.read_sql_query("SELECT * FROM facilities", conn)

        product_df = pd.read_sql_query(
            "SELECT * FROM products WHERE product_id = ?",
            conn,
            params=[str(product_id)],
        )

        if len(product_df) == 0:
            fallback_df = pd.read_sql_query("SELECT * FROM products LIMIT 1", conn)
            if len(fallback_df) > 0:
                product_id = fallback_df.iloc[0]["product_id"]
                product_df = fallback_df

        # Aggregate daily demand across all facilities for target SKU
        demand_df = pd.read_sql_query(
            """
            SELECT date, SUM(demand_qty) AS total_retail_demand
            FROM historical_demand
            WHERE product_id = ?
            GROUP BY date
            ORDER BY date ASC
            LIMIT ?
            """,
            conn,
            params=[str(product_id), int(horizon_days)],
        )

        # Current inventory snapshots
        snapshot_df = pd.read_sql_query(
            """
            SELECT s.*, f.echelon_id, e.echelon_tier, e.echelon_name
            FROM inventory_snapshot s
            JOIN facilities f ON s.facility_id = f.facility_id
            JOIN echelons e ON f.echelon_id = e.echelon_id
            WHERE s.product_id = ?
            """,
            conn,
            params=[str(product_id)],
        )

        # Compute baseline starting inventory per tier
        initial_inv = []
        for tier in [1, 2, 3]:
            tier_snapshots = snapshot_df[snapshot_df["echelon_tier"] == tier]
            if len(tier_snapshots) > 0 and tier_snapshots["starting_inventory"].sum() > 0:
                initial_inv.append(float(tier_snapshots["starting_inventory"].sum()))
            else:
                avg_demand = float(demand_df["total_retail_demand"].mean()) if len(demand_df) > 0 else 100.0
                mult = 20.0 if tier == 1 else (6.0 if tier == 2 else 2.0)
                initial_inv.append(round(avg_demand * mult, 1))

        return {
            "product_id": str(product_id),
            "echelons": echelons_df,
            "facilities": facilities_df,
            "product": product_df.iloc[0].to_dict() if len(product_df) > 0 else {},
            "demand": demand_df.sort_values("date").reset_index(drop=True),
            "snapshot": snapshot_df,
            "initial_inventory": initial_inv,
        }
    finally:
        conn.close()


def ensure_database_ready(db_path=DB_FILE, reseed=False):
    """Ensure database exists and is populated with real supply chain data."""
    need_seed = reseed or not os.path.exists(db_path)
    if not need_seed:
        try:
            conn = get_connection(db_path)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM historical_demand")
                count = cur.fetchone()[0]
                if count == 0:
                    need_seed = True
            finally:
                conn.close()
        except Exception:
            need_seed = True

    if need_seed:
        init_database(db_path)
        seed_master_data(db_path)


if __name__ == "__main__":
    init_database()
    seed_master_data()
    prods = get_available_products()
    print(f"Total products available: {len(prods)}")
    sample = load_dataset_for_optimizer(product_id="SKU_1", horizon_days=30)
    print("Demand sample head:")
    print(sample["demand"].head())
    print("Initial Inventory per tier:", sample["initial_inventory"])
