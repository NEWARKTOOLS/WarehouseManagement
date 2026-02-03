"""
Migration to add costing/production fields to items table
Integrates parts with costing system
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

# Add costing fields to items table
migrations = [
    # Part weight and runner info
    ("items", "part_weight_grams", "ALTER TABLE items ADD COLUMN part_weight_grams FLOAT"),
    ("items", "runner_weight_grams", "ALTER TABLE items ADD COLUMN runner_weight_grams FLOAT"),
    ("items", "shot_weight_grams", "ALTER TABLE items ADD COLUMN shot_weight_grams FLOAT"),  # Total shot

    # Material info
    ("items", "material_type", "ALTER TABLE items ADD COLUMN material_type VARCHAR(50)"),  # PP, ABS, PA6, etc
    ("items", "material_id", "ALTER TABLE items ADD COLUMN material_id INTEGER REFERENCES items(id)"),  # Link to raw material item
    ("items", "masterbatch_id", "ALTER TABLE items ADD COLUMN masterbatch_id INTEGER REFERENCES items(id)"),  # Link to masterbatch
    ("items", "masterbatch_ratio", "ALTER TABLE items ADD COLUMN masterbatch_ratio VARCHAR(20)"),  # e.g. "3%"
    ("items", "regrind_percent", "ALTER TABLE items ADD COLUMN regrind_percent FLOAT DEFAULT 0"),

    # Production info
    ("items", "cavities", "ALTER TABLE items ADD COLUMN cavities INTEGER DEFAULT 1"),
    ("items", "ideal_cycle_time", "ALTER TABLE items ADD COLUMN ideal_cycle_time FLOAT"),  # Ideal/target cycle time
    ("items", "setup_time_hours", "ALTER TABLE items ADD COLUMN setup_time_hours FLOAT DEFAULT 2"),

    # Costing defaults
    ("items", "material_cost_per_kg", "ALTER TABLE items ADD COLUMN material_cost_per_kg FLOAT"),
    ("items", "target_machine_rate", "ALTER TABLE items ADD COLUMN target_machine_rate FLOAT"),
    ("items", "target_margin_percent", "ALTER TABLE items ADD COLUMN target_margin_percent FLOAT DEFAULT 30"),

    # Machine rates table updates
    ("machine_rates", "notes", "ALTER TABLE machine_rates ADD COLUMN notes TEXT"),
]

for table, column, sql in migrations:
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

conn.commit()
conn.close()
print("\nItem costing fields migration complete!")
