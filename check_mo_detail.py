"""
Script untuk cek detail lengkap salah satu MO batch
"""
from sqlalchemy import create_engine, text

from app.core.config import get_settings


def check_batch_detail():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    print("=" * 70)
    print("MO Batch Detail - Checking Silo Mapping")
    print("=" * 70)
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT 
                batch_no,
                mo_id,
                consumption,
                equipment_id_batch,
                component_silo_a_name, consumption_silo_a,
                component_silo_b_name, consumption_silo_b,
                component_silo_c_name, consumption_silo_c,
                component_silo_d_name, consumption_silo_d,
                component_silo_e_name, consumption_silo_e,
                component_silo_f_name, consumption_silo_f,
                component_silo_g_name, consumption_silo_g,
                component_silo_h_name, consumption_silo_h,
                component_silo_i_name, consumption_silo_i,
                component_silo_j_name, consumption_silo_j,
                component_silo_k_name, consumption_silo_k,
                component_silo_l_name, consumption_silo_l,
                component_silo_m_name, consumption_silo_m
            FROM mo_batch 
            WHERE batch_no = 1
            """)
        )
        
        row = result.fetchone()
        if row:
            print(f"\nBatch #{row.batch_no}: {row.mo_id}")
            print(f"Equipment: {row.equipment_id_batch}")
            print(f"Total Consumption: {row.consumption} kg")
            print("\nComponent Consumption by Silo:")
            print("-" * 70)
            
            silos = [
                ('A', row.component_silo_a_name, row.consumption_silo_a),
                ('B', row.component_silo_b_name, row.consumption_silo_b),
                ('C', row.component_silo_c_name, row.consumption_silo_c),
                ('D', row.component_silo_d_name, row.consumption_silo_d),
                ('E', row.component_silo_e_name, row.consumption_silo_e),
                ('F', row.component_silo_f_name, row.consumption_silo_f),
                ('G', row.component_silo_g_name, row.consumption_silo_g),
                ('H', row.component_silo_h_name, row.consumption_silo_h),
                ('I', row.component_silo_i_name, row.consumption_silo_i),
                ('J', row.component_silo_j_name, row.consumption_silo_j),
                ('K', row.component_silo_k_name, row.consumption_silo_k),
                ('L', row.component_silo_l_name, row.consumption_silo_l),
                ('M', row.component_silo_m_name, row.consumption_silo_m),
            ]
            
            for silo_letter, component_name, consumption in silos:
                if component_name:
                    print(f"  Silo {silo_letter} (101+{ord(silo_letter)-65}): {component_name:25} → {consumption:8.2f} kg")
                else:
                    print(f"  Silo {silo_letter} (101+{ord(silo_letter)-65}): {'[empty]':25} → {'-':>8}")
    
    print("\n" + "=" * 70)
    print("Detail check completed!")
    print("=" * 70)


if __name__ == "__main__":
    check_batch_detail()
