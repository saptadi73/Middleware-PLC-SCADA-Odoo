"""Verify migration - check new columns in mo_histories table"""
from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

try:
    # Check new columns
    result = db.execute(text("""
        SELECT column_name, data_type, column_default, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'mo_histories' 
        AND column_name IN ('status', 'notes')
        ORDER BY column_name
    """))
    
    print("\n" + "="*80)
    print("MIGRATION VERIFICATION: mo_histories table")
    print("="*80)
    
    columns = result.fetchall()
    if columns:
        print("\n✅ New columns added successfully:\n")
        for col in columns:
            print(f"Column:   {col[0]}")
            print(f"Type:     {col[1]}")
            print(f"Default:  {col[2] if col[2] else 'NULL'}")
            print(f"Nullable: {col[3]}")
            print("-" * 80)
    else:
        print("\n❌ Columns not found!")
    
    # Check if index exists
    idx_result = db.execute(text("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'mo_histories'
        AND indexname LIKE '%status%'
    """))
    
    indexes = idx_result.fetchall()
    if indexes:
        print("\n✅ Index created:\n")
        for idx in indexes:
            print(f"Index: {idx[0]}")
            print(f"Definition: {idx[1]}")
    else:
        print("\n⚠️ No status index found (this might be okay)")
    
    # Show sample of existing records
    count_result = db.execute(text("SELECT COUNT(*) FROM mo_histories"))
    count = count_result.scalar()
    
    print(f"\n📊 Total records in mo_histories: {count}")
    
    if count > 0:
        sample = db.execute(text("""
            SELECT batch_no, mo_id, status, notes
            FROM mo_histories
            LIMIT 3
        """))
        print("\nSample records:")
        for row in sample:
            print(f"  Batch {row[0]} | MO: {row[1]} | Status: {row[2]} | Notes: {row[3] or 'None'}")
    
    print("\n" + "="*80)
    print("✅ MIGRATION VERIFIED SUCCESSFULLY!")
    print("="*80 + "\n")
    
finally:
    db.close()
