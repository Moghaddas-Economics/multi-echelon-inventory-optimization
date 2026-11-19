-- MultiEchelonDSS Database Schema
-- Multi-Echelon Inventory and Distribution Optimization Decision Support System
-- Relational Database Subsystem (Sprague 1980 compliant)

CREATE TABLE IF NOT EXISTS echelons (
    echelon_id INTEGER PRIMARY KEY,
    echelon_name TEXT NOT NULL,
    echelon_tier INTEGER NOT NULL, -- 1: Supplier, 2: Warehouse/DC, 3: Retailer
    lead_time_days INTEGER NOT NULL,
    holding_cost_per_unit REAL NOT NULL,
    order_fixed_cost REAL NOT NULL,
    stockout_penalty_per_unit REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS facilities (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT NOT NULL,
    echelon_id INTEGER NOT NULL,
    location TEXT NOT NULL,
    max_capacity INTEGER NOT NULL,
    FOREIGN KEY (echelon_id) REFERENCES echelons(echelon_id)
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    unit_cost REAL NOT NULL,
    selling_price REAL NOT NULL,
    min_order_qty INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS historical_demand (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    demand_qty INTEGER NOT NULL,
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS inventory_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    starting_inventory INTEGER NOT NULL,
    in_transit_qty INTEGER NOT NULL,
    safety_stock INTEGER NOT NULL,
    reorder_point INTEGER NOT NULL,
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS optimization_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TEXT NOT NULL,
    period_t INTEGER NOT NULL,
    facility_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    recommended_order_qty REAL NOT NULL,
    projected_inventory REAL NOT NULL,
    projected_stockout REAL NOT NULL,
    holding_cost REAL NOT NULL,
    order_cost REAL NOT NULL,
    penalty_cost REAL NOT NULL,
    policy_type TEXT NOT NULL, -- 'OPTIMIZED_MULTI_ECHELON' vs 'TRADITIONAL_SINGLE'
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Performance indices
CREATE INDEX IF NOT EXISTS idx_demand_product_date ON historical_demand(product_id, date);
CREATE INDEX IF NOT EXISTS idx_snapshot_product ON inventory_snapshot(product_id);
CREATE INDEX IF NOT EXISTS idx_facilities_echelon ON facilities(echelon_id);
