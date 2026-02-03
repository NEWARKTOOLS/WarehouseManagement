"""
Migration script for Job Costing & Profitability tables
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'warehouse.db')

if not os.path.exists(db_path):
    print(f"Database not found at: {db_path}")
    exit(1)

print(f"Connecting to: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create new tables for costing system
tables = [
    # Job Costing - track actual costs per production order
    """
    CREATE TABLE IF NOT EXISTS job_costings (
        id INTEGER PRIMARY KEY,
        production_order_id INTEGER NOT NULL UNIQUE REFERENCES production_orders(id),

        -- Quoted/Expected costs
        quoted_material_cost FLOAT DEFAULT 0,
        quoted_labour_cost FLOAT DEFAULT 0,
        quoted_machine_cost FLOAT DEFAULT 0,
        quoted_overhead_cost FLOAT DEFAULT 0,
        quoted_total_cost FLOAT DEFAULT 0,
        quoted_selling_price FLOAT DEFAULT 0,

        -- Actual costs
        actual_material_cost FLOAT DEFAULT 0,
        actual_material_kg FLOAT DEFAULT 0,
        actual_labour_cost FLOAT DEFAULT 0,
        actual_labour_hours FLOAT DEFAULT 0,
        actual_machine_cost FLOAT DEFAULT 0,
        actual_machine_hours FLOAT DEFAULT 0,
        actual_setup_hours FLOAT DEFAULT 0,
        actual_overhead_cost FLOAT DEFAULT 0,

        -- Scrap/waste
        scrap_quantity FLOAT DEFAULT 0,
        scrap_cost FLOAT DEFAULT 0,
        rework_hours FLOAT DEFAULT 0,
        rework_cost FLOAT DEFAULT 0,

        -- Energy
        energy_kwh FLOAT DEFAULT 0,
        energy_cost FLOAT DEFAULT 0,

        -- Tooling
        tooling_cost FLOAT DEFAULT 0,

        -- Final selling price
        actual_selling_price FLOAT DEFAULT 0,

        -- Timestamps
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME
    )
    """,

    # Material Usage - track material usage per job
    """
    CREATE TABLE IF NOT EXISTS material_usage (
        id INTEGER PRIMARY KEY,
        production_order_id INTEGER NOT NULL REFERENCES production_orders(id),
        item_id INTEGER REFERENCES items(id),

        material_type VARCHAR(100),
        material_grade VARCHAR(100),
        supplier VARCHAR(200),
        batch_number VARCHAR(100),

        quantity_issued_kg FLOAT DEFAULT 0,
        quantity_used_kg FLOAT DEFAULT 0,
        quantity_returned_kg FLOAT DEFAULT 0,
        quantity_scrap_kg FLOAT DEFAULT 0,

        cost_per_kg FLOAT DEFAULT 0,
        total_cost FLOAT DEFAULT 0,

        masterbatch_type VARCHAR(100),
        masterbatch_ratio VARCHAR(50),
        masterbatch_kg FLOAT DEFAULT 0,
        masterbatch_cost FLOAT DEFAULT 0,

        regrind_percentage FLOAT DEFAULT 0,
        regrind_kg FLOAT DEFAULT 0,

        issued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Machine Rates - hourly rates for costing
    """
    CREATE TABLE IF NOT EXISTS machine_rates (
        id INTEGER PRIMARY KEY,
        machine_id INTEGER NOT NULL REFERENCES machines(id),

        hourly_rate FLOAT DEFAULT 0,
        setup_rate FLOAT DEFAULT 0,
        energy_rate_per_kwh FLOAT DEFAULT 0.15,

        idle_kw FLOAT DEFAULT 0,
        running_kw FLOAT DEFAULT 0,

        overhead_rate_per_hour FLOAT DEFAULT 0,

        effective_from DATE NOT NULL,
        effective_to DATE,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Labour Rates
    """
    CREATE TABLE IF NOT EXISTS labour_rates (
        id INTEGER PRIMARY KEY,
        role VARCHAR(100) NOT NULL,
        hourly_rate FLOAT DEFAULT 0,
        overtime_multiplier FLOAT DEFAULT 1.5,

        effective_from DATE NOT NULL,
        effective_to DATE,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Quotes
    """
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY,
        quote_number VARCHAR(50) UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        item_id INTEGER REFERENCES items(id),

        description VARCHAR(500),
        quantity FLOAT NOT NULL,
        annual_volume FLOAT,

        part_weight_g FLOAT,
        runner_weight_g FLOAT,
        cycle_time_seconds FLOAT,
        cavities INTEGER DEFAULT 1,

        material_type VARCHAR(100),
        material_cost_per_kg FLOAT DEFAULT 0,
        material_cost_per_part FLOAT DEFAULT 0,

        machine_rate_per_hour FLOAT DEFAULT 0,
        labour_rate_per_hour FLOAT DEFAULT 0,
        cycle_cost_per_part FLOAT DEFAULT 0,

        setup_hours FLOAT DEFAULT 0,
        setup_cost FLOAT DEFAULT 0,
        setup_cost_per_part FLOAT DEFAULT 0,

        secondary_ops_cost FLOAT DEFAULT 0,

        overhead_percent FLOAT DEFAULT 20,
        overhead_cost_per_part FLOAT DEFAULT 0,

        packaging_cost_per_part FLOAT DEFAULT 0,

        total_cost_per_part FLOAT DEFAULT 0,
        target_margin_percent FLOAT DEFAULT 30,
        quoted_price_per_part FLOAT DEFAULT 0,
        quoted_total FLOAT DEFAULT 0,

        tooling_cost FLOAT DEFAULT 0,
        tooling_amortization_qty FLOAT,

        status VARCHAR(30) DEFAULT 'draft',
        valid_until DATE,

        notes TEXT,
        internal_notes TEXT,

        sales_order_id INTEGER REFERENCES sales_orders(id),

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        sent_at DATETIME
    )
    """,

    # Customer Profitability
    """
    CREATE TABLE IF NOT EXISTS customer_profitability (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        period_year INTEGER NOT NULL,
        period_month INTEGER,

        total_revenue FLOAT DEFAULT 0,
        order_count INTEGER DEFAULT 0,

        total_material_cost FLOAT DEFAULT 0,
        total_labour_cost FLOAT DEFAULT 0,
        total_machine_cost FLOAT DEFAULT 0,
        total_overhead_cost FLOAT DEFAULT 0,
        total_cost FLOAT DEFAULT 0,

        gross_profit FLOAT DEFAULT 0,
        gross_margin_percent FLOAT DEFAULT 0,

        avg_order_value FLOAT DEFAULT 0,
        on_time_delivery_percent FLOAT DEFAULT 0,
        reject_rate_percent FLOAT DEFAULT 0,

        calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
]

# Create tables
for sql in tables:
    try:
        cursor.execute(sql)
        # Extract table name from CREATE TABLE statement
        table_name = sql.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
        print(f"  [OK] Created/verified table: {table_name}")
    except Exception as e:
        print(f"  [ERROR] {e}")

# Create indexes for better performance
indexes = [
    "CREATE INDEX IF NOT EXISTS idx_job_costings_po ON job_costings(production_order_id)",
    "CREATE INDEX IF NOT EXISTS idx_material_usage_po ON material_usage(production_order_id)",
    "CREATE INDEX IF NOT EXISTS idx_machine_rates_machine ON machine_rates(machine_id)",
    "CREATE INDEX IF NOT EXISTS idx_quotes_customer ON quotes(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_quotes_number ON quotes(quote_number)",
    "CREATE INDEX IF NOT EXISTS idx_customer_profitability_customer ON customer_profitability(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_customer_profitability_period ON customer_profitability(period_year, period_month)",
]

print("\nCreating indexes...")
for sql in indexes:
    try:
        cursor.execute(sql)
        print(f"  [OK] {sql.split('idx_')[1].split(' ')[0]}")
    except Exception as e:
        print(f"  [ERROR] {e}")

conn.commit()
conn.close()
print("\nCosting tables migration complete!")
