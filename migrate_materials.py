"""
Migration script for Materials Management tables
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

# Create materials tables
tables = [
    # Material Suppliers
    """
    CREATE TABLE IF NOT EXISTS material_suppliers (
        id INTEGER PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        code VARCHAR(20) UNIQUE,

        contact_name VARCHAR(100),
        email VARCHAR(120),
        phone VARCHAR(30),
        website VARCHAR(200),

        address_line1 VARCHAR(200),
        address_line2 VARCHAR(200),
        city VARCHAR(100),
        postcode VARCHAR(20),
        country VARCHAR(100) DEFAULT 'UK',

        account_number VARCHAR(50),
        payment_terms VARCHAR(100),
        lead_time_days INTEGER,
        minimum_order_kg FLOAT,

        notes TEXT,
        is_active BOOLEAN DEFAULT 1,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Materials
    """
    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        code VARCHAR(50) UNIQUE NOT NULL,

        material_type VARCHAR(50) NOT NULL,
        grade VARCHAR(100),
        manufacturer VARCHAR(100),

        supplier_id INTEGER REFERENCES material_suppliers(id),
        supplier_code VARCHAR(100),

        mfi FLOAT,
        density FLOAT,
        color VARCHAR(50),

        cost_per_kg FLOAT NOT NULL,
        currency VARCHAR(3) DEFAULT 'GBP',
        last_price_update DATE,

        current_stock_kg FLOAT DEFAULT 0,
        min_stock_kg FLOAT,
        reorder_qty_kg FLOAT,

        item_id INTEGER REFERENCES items(id),

        barrel_temp_min INTEGER,
        barrel_temp_max INTEGER,
        mould_temp_min INTEGER,
        mould_temp_max INTEGER,
        drying_required BOOLEAN DEFAULT 0,
        drying_temp INTEGER,
        drying_time_hours FLOAT,

        datasheet_filename VARCHAR(255),

        notes TEXT,
        is_active BOOLEAN DEFAULT 1,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Material Price History
    """
    CREATE TABLE IF NOT EXISTS material_price_history (
        id INTEGER PRIMARY KEY,
        material_id INTEGER NOT NULL REFERENCES materials(id),

        cost_per_kg FLOAT NOT NULL,
        effective_date DATE NOT NULL,

        reason VARCHAR(200),
        notes TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by VARCHAR(100)
    )
    """,

    # Masterbatches
    """
    CREATE TABLE IF NOT EXISTS masterbatches (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(200) NOT NULL,
        color VARCHAR(50),
        color_code VARCHAR(20),

        supplier_id INTEGER REFERENCES material_suppliers(id),
        supplier_code VARCHAR(100),

        compatible_materials VARCHAR(200),

        typical_ratio_percent FLOAT DEFAULT 3,
        min_ratio_percent FLOAT,
        max_ratio_percent FLOAT,

        cost_per_kg FLOAT,

        current_stock_kg FLOAT DEFAULT 0,
        min_stock_kg FLOAT,

        item_id INTEGER REFERENCES items(id),

        notes TEXT,
        is_active BOOLEAN DEFAULT 1,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
]

# Create tables
for sql in tables:
    try:
        cursor.execute(sql)
        table_name = sql.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
        print(f"  [OK] Created/verified table: {table_name}")
    except Exception as e:
        print(f"  [ERROR] {e}")

# Add material_id foreign key to items table if not exists
item_migrations = [
    ("items", "linked_material_id", "ALTER TABLE items ADD COLUMN linked_material_id INTEGER REFERENCES materials(id)"),
    ("items", "linked_masterbatch_id", "ALTER TABLE items ADD COLUMN linked_masterbatch_id INTEGER REFERENCES masterbatches(id)"),
]

print("\nAdding item links...")
for table, column, sql in item_migrations:
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column in columns:
            print(f"  [SKIP] {table}.{column} already exists")
        else:
            cursor.execute(sql)
            print(f"  [OK] Added {table}.{column}")
    except Exception as e:
        print(f"  [ERROR] {table}.{column}: {e}")

# Create indexes
indexes = [
    "CREATE INDEX IF NOT EXISTS idx_materials_type ON materials(material_type)",
    "CREATE INDEX IF NOT EXISTS idx_materials_supplier ON materials(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_material_price_history ON material_price_history(material_id, effective_date)",
    "CREATE INDEX IF NOT EXISTS idx_masterbatches_supplier ON masterbatches(supplier_id)",
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
print("\nMaterials tables migration complete!")
