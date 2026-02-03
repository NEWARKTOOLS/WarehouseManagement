"""
Database migration script - Run this once to add new columns
Usage: python migrate_db.py
"""

from app import create_app, db

def run_migrations():
    app = create_app()

    with app.app_context():
        migrations = [
            # Customer link for items
            ("items", "customer_id", "ALTER TABLE items ADD COLUMN customer_id INTEGER REFERENCES customers(id)"),

            # Profile picture for users
            ("users", "avatar_filename", "ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255)"),

            # Packing list settings
            ("company_settings", "packing_list_title", "ALTER TABLE company_settings ADD COLUMN packing_list_title VARCHAR(100) DEFAULT 'PACKING LIST'"),
            ("company_settings", "packing_list_show_prices", "ALTER TABLE company_settings ADD COLUMN packing_list_show_prices BOOLEAN DEFAULT 0"),
            ("company_settings", "packing_list_show_signature", "ALTER TABLE company_settings ADD COLUMN packing_list_show_signature BOOLEAN DEFAULT 1"),
            ("company_settings", "packing_list_show_bank_details", "ALTER TABLE company_settings ADD COLUMN packing_list_show_bank_details BOOLEAN DEFAULT 0"),
        ]

        for table, column, sql in migrations:
            try:
                # Check if column already exists
                result = db.session.execute(db.text(f"PRAGMA table_info({table})"))
                columns = [row[1] for row in result.fetchall()]

                if column in columns:
                    print(f"  [SKIP] {table}.{column} already exists")
                else:
                    db.session.execute(db.text(sql))
                    print(f"  [OK] Added {table}.{column}")
            except Exception as e:
                print(f"  [ERROR] {table}.{column}: {e}")

        db.session.commit()
        print("\nMigration complete!")

if __name__ == "__main__":
    print("Running database migrations...\n")
    run_migrations()
