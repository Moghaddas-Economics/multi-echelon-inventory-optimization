# MultiEchelonDSS — System Architecture Specification

## 🏛️ Sprague (1980) Three-Subsystem DSS Framework

This Decision Support System (DSS) follows the classical **Sprague (1980)** tripartite architecture, integrating **Data Management**, **Model Management**, and **Dialogue (User Interface)** subsystems to solve multi-echelon inventory allocation under stochastic demand.

```mermaid
flowchart TD
    subgraph EXT["External Environment & Raw Data Sources"]
        CSV["Dataset/supply_chain_dataset1.csv (91,250 records, 50 SKUs)"]
        PARAM["Cost Matrices & Lead Times (Holding, Penalty, Order Costs)"]
    end

    subgraph DSS_DB["1. Database Management Subsystem (Sprague, 1980)"]
        ETL["database/db_manager.py (ETL Ingestion Engine)"]
        SQLITE[("database/multiechelon_dss.db (SQLite Store)")]
        T_ECH["Table: echelons (Tiers 1, 2, 3 facilities)"]
        T_PROD["Table: products (SKU_1 to SKU_50)"]
        T_DEM["Table: demand_records (Historical POS demand)"]
        T_INV["Table: inventory_snapshots (Daily tracking)"]
    end

    subgraph DSS_MB["2. Model Base Management Subsystem (Sprague, 1980)"]
        SOLVER["models/optimizer.py (MultiEchelonOptimizer Engine)"]
        LP["Linear Program (scipy.optimize.linprog HiGHS)"]
        TRAD["Traditional Single-Echelon (s, S) Policy Simulator"]
        EVAL["Policy Comparator & Bullwhip Analyzer (sigma Q / sigma D)"]
    end

    subgraph PHYS["Multi-Echelon Physical Flow Conduit"]
        T1["Tier 1: 10 Central Plants (Lead Time = 7d, Holding = $1.50)"]
        T2["Tier 2: 5 Regional DCs (Lead Time = 3d, Holding = $3.00)"]
        T3["Tier 3: 4 Retail Outlets (Lead Time = 1d, Holding = $6.00)"]
        CONS["End Customer Demand (Stochastic POS Consumption)"]
    end

    subgraph DSS_DG["3. Dialogue / User Interface Subsystem (Sprague, 1980)"]
        APP["app.py (Streamlit Reactive Dashboard :8525)"]
        TAB1["Tab 1: Executive Cockpit & Sankey Network Flows"]
        TAB2["Tab 2: Inventory Trajectories & Health Matrix Heatmap"]
        TAB3["Tab 3: Simon (1960) PO Replenishment Guidance"]
        TAB4["Tab 4: What-If Sensitivity & Policy Simulator"]
        TAB5["Tab 5: Mathematical LP & Theoretical Architecture"]
        PBI["exports/export_powerbi.py (Power BI Automated Exports)"]
    end

    CSV --> ETL
    PARAM --> ETL
    ETL --> SQLITE
    SQLITE --> T_ECH & T_PROD & T_DEM & T_INV

    T_ECH & T_DEM --> SOLVER
    SOLVER --> LP
    SOLVER --> TRAD
    LP & TRAD --> EVAL

    T1 --"Shipments (Lead Time = 7d)"--> T2
    T2 --"Transfers (Lead Time = 3d)"--> T3
    T3 --"Point-of-Sale Fulfillments"--> CONS

    EVAL --> APP
    APP --> TAB1 & TAB2 & TAB3 & TAB4 & TAB5
    APP --> PBI
```

---

## 🔄 Herbert Simon (1960) Four-Phase Decision Process

```mermaid
flowchart LR
    subgraph P1["1. Intelligence Phase"]
        I1["Ingest POS Historical Sales"] --> I2["Identify Stockout & Bullwhip Risks"]
        I2 --> I3["Detect Inventory Buffer Breaches"]
    end

    subgraph P2["2. Design Phase"]
        D1["Formulate Multi-Echelon LP Objective"]
        D2["Construct Balance & Capacity Constraints"]
        D3["Simulate Traditional (s, S) Baseline"]
    end

    subgraph P3["3. Choice Phase"]
        C1["Solve via HiGHS Simplex / IPM"]
        C2["Select Optimal Order Vector Q*(t)"]
        C3["Perform Real-Time What-If Sensitivity"]
    end

    subgraph P4["4. Implementation Phase"]
        M1["Generate Priority-Ranked PO Schedule"]
        M2["Deliver Explainable Justifications"]
        M3["Export Datasets to Power BI / ERP"]
    end

    P1 --> P2
    P2 --> P3
    P3 --> P4
```

---

## 📦 Subsystem Component Matrix

| Subsystem | Primary Code File | Key Functions / Responsibilities |
| :--- | :--- | :--- |
| **Data Management** | `database/db_manager.py`<br>`database/schema.sql` | Schema creation, ETL from CSV, dynamic parameter querying, horizon slicing. |
| **Model Management** | `models/optimizer.py` | Multi-echelon linear program formulation, sparse matrix assembly, HiGHS solver invocation, $(s,S)$ traditional simulation, Bullwhip variance ratio calculation. |
| **Dialogue Subsystem** | `app.py`<br>`exports/export_powerbi.py` | Dark cyber-glass UI, Plotly Sankey flow charts, heatmap health matrices, what-if sliders, CSV operational schedules. |

