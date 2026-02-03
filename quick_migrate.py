"""
Quick database migration - runs directly on SQLite without loading Flask app
"""
import sqlite3
import os

# Find database file
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'warehouse.db')

if not os.path.exists(db_path):
    print(f"Database not found at: {db_path}")
    exit(1)

print(f"Connecting to: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

migrations = [
    ("users", "avatar_filename", "ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255)"),
    ("items", "customer_id", "ALTER TABLE items ADD COLUMN customer_id INTEGER REFERENCES customers(id)"),
    ("company_settings", "packing_list_title", "ALTER TABLE company_settings ADD COLUMN packing_list_title VARCHAR(100) DEFAULT 'PACKING LIST'"),
    ("company_settings", "packing_list_show_prices", "ALTER TABLE company_settings ADD COLUMN packing_list_show_prices BOOLEAN DEFAULT 0"),
    ("company_settings", "packing_list_show_signature", "ALTER TABLE company_settings ADD COLUMN packing_list_show_signature BOOLEAN DEFAULT 1"),
    ("company_settings", "packing_list_show_bank_details", "ALTER TABLE company_settings ADD COLUMN packing_list_show_bank_details BOOLEAN DEFAULT 0"),
    # Order enhancements - shipping cost and custom items
    ("sales_orders", "shipping_cost", "ALTER TABLE sales_orders ADD COLUMN shipping_cost FLOAT DEFAULT 0"),
    ("sales_order_lines", "custom_sku", "ALTER TABLE sales_order_lines ADD COLUMN custom_sku VARCHAR(100)"),
    ("sales_order_lines", "custom_description", "ALTER TABLE sales_order_lines ADD COLUMN custom_description VARCHAR(500)"),
    ("sales_order_lines", "is_custom_item", "ALTER TABLE sales_order_lines ADD COLUMN is_custom_item BOOLEAN DEFAULT 0"),
    # Machine layout fields
    ("machines", "display_order", "ALTER TABLE machines ADD COLUMN display_order INTEGER DEFAULT 0"),
    ("machines", "position_x", "ALTER TABLE machines ADD COLUMN position_x INTEGER"),
    ("machines", "position_y", "ALTER TABLE machines ADD COLUMN position_y INTEGER"),
    # Setup sheet PDF upload
    ("setup_sheets", "setup_sheet_pdf", "ALTER TABLE setup_sheets ADD COLUMN setup_sheet_pdf VARCHAR(255)"),
    # Production order customer link
    ("production_orders", "customer_id", "ALTER TABLE production_orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)"),
    # Item default mould
    ("items", "default_mould_id", "ALTER TABLE items ADD COLUMN default_mould_id INTEGER REFERENCES moulds(id)"),
]

for table, column, sql in migrations:
    try:
        # Check if column exists
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
print("\nMigration complete! Try running the app now.")
