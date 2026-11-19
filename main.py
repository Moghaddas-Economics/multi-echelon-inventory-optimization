"""
MultiEchelonDSS — Main Pipeline Orchestrator
Decision Support System for Multi-Echelon Inventory & Distribution Optimization
Sprague (1980) Compliant Architecture
"""

import sys
import os
import argparse
from database.db_manager import (
    init_database,
    seed_master_data,
    ensure_database_ready,
    load_dataset_for_optimizer,
    get_available_products,
)
from models.optimizer import MultiEchelonOptimizer
from exports.export_powerbi import export_all_powerbi_datasets


def run_pipeline(product_id="SKU_1", horizon_days=30, reseed=False):
    """Executes the full Decision Support System pipeline on the real supply chain dataset."""
    print("=" * 70)
    print("  MultiEchelonDSS: Multi-Echelon Inventory Optimization DSS")
    print("  Framework: Sprague (1980) Model-Driven + Data-Driven DSS")
    print("=" * 70)

    # 1. Database Subsystem
    print("\n[Step 1/3] Database Subsystem: Checking database status...")
    db_path = os.path.join(os.path.dirname(__file__), "database", "multiechelon_dss.db")
    ensure_database_ready(db_path=db_path, reseed=reseed)

    products = get_available_products(db_path=db_path)
    print(f"  Connected to SQLite database: {db_path}")
    print(f"  Available Products: {len(products)} SKUs (SKU_1 to SKU_50)")

    # 2. Model Base Subsystem
    print(f"\n[Step 2/3] Model Base Subsystem: Solving optimization model for {product_id}...")
    dataset = load_dataset_for_optimizer(product_id=product_id, horizon_days=horizon_days)
    demand = dataset["demand"]["total_retail_demand"].tolist()
    echelons = dataset["echelons"]
    prod_info = dataset.get("product", {})
    init_inv = dataset.get("initial_inventory")

    if len(demand) == 0:
        print(f"  [Error] No demand data found for SKU '{product_id}'.")
        return

    print(f"  Product Name                 : {prod_info.get('product_name', product_id)}")
    print(f"  Unit Cost                    : ${prod_info.get('unit_cost', 0):.2f}")
    print(f"  Selling Price                : ${prod_info.get('selling_price', 0):.2f}")
    print(f"  Starting Multi-Tier Inventory: Plant={init_inv[0]:,.0f}, DC={init_inv[1]:,.0f}, Retail={init_inv[2]:,.0f}")

    optimizer = MultiEchelonOptimizer(echelons, demand, initial_inventory=init_inv, horizon_days=horizon_days)
    comparison = optimizer.compare_policies()
    metrics = comparison["metrics"]

    print("\n" + "-" * 70)
    print("  DECISION SUPPORT METRICS SUMMARY")
    print("-" * 70)
    print(f"  Target Product               : {product_id}")
    print(f"  Planning Horizon             : {optimizer.T} days")
    print(f"  Avg Daily Retail Demand      : {sum(demand)/len(demand):.1f} units/day")
    print(f"  Traditional Policy Total Cost: ${metrics['total_traditional_cost']:,.2f}")
    print(f"  Optimized Policy Total Cost  : ${metrics['total_optimized_cost']:,.2f}")
    print(f"  Cost Savings Achieved        : ${metrics['cost_savings_amount']:,.2f} ({metrics['cost_savings_percentage']:.1f}%)")
    print(f"  Traditional Bullwhip Ratio   : {metrics['traditional_bullwhip_ratio']:.2f}")
    print(f"  Optimized Bullwhip Ratio     : {metrics['optimized_bullwhip_ratio']:.2f}")
    print(f"  Bullwhip Variance Reduction  : {metrics['bullwhip_reduction_pct']:.1f}%")
    print("-" * 70)

    # 3. Export Subsystem (Power BI Integration)
    print("\n[Step 3/3] Export Subsystem: Generating Power BI CSV datasets...")
    exports = export_all_powerbi_datasets(product_id=product_id, horizon_days=horizon_days)
    print(f"  Inventory Flows : {exports['flows_path']}")
    print(f"  KPI Summary     : {exports['kpi_path']}")
    print(f"  Replenishment PO: {exports['sched_path']}")

    print("\n" + "=" * 70)
    print("  PIPELINE EXECUTION COMPLETE!")
    print("  To launch the interactive DSS Dashboard, run:")
    print("     streamlit run app.py")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MultiEchelonDSS Master Pipeline Orchestrator")
    parser.add_argument("--sku", type=str, default="SKU_1", help="Target Product SKU (e.g. SKU_1, SKU_2, ... SKU_50)")
    parser.add_argument("--horizon", type=int, default=30, help="Planning horizon in days (default: 30)")
    parser.add_argument("--reseed", action="store_true", help="Re-ingest dataset from CSV into SQLite database")
    args = parser.parse_args()

    run_pipeline(product_id=args.sku, horizon_days=args.horizon, reseed=args.reseed)
