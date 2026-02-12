from sqlalchemy import Boolean, Column, Float, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class TableSmoBatch(Base):
    __tablename__ = "mo_batch"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    batch_no = Column(Integer, nullable=False, index=True)
    mo_id = Column(String(64), nullable=False)
    consumption = Column(Numeric(18, 3), nullable=False)
    equipment_id_batch = Column(String(64), nullable=False)

    silo_a = Column(Integer, nullable=False, server_default="101")
    component_silo_a_name = Column(String(64), nullable=True)
    consumption_silo_a = Column(Float, nullable=True)
    silo_b = Column(Integer, nullable=False, server_default="102")
    component_silo_b_name = Column(String(64), nullable=True)
    consumption_silo_b = Column(Float, nullable=True)
    silo_c = Column(Integer, nullable=False, server_default="103")
    component_silo_c_name = Column(String(64), nullable=True)
    consumption_silo_c = Column(Float, nullable=True)
    silo_d = Column(Integer, nullable=False, server_default="104")
    component_silo_d_name = Column(String(64), nullable=True)
    consumption_silo_d = Column(Float, nullable=True)
    silo_e = Column(Integer, nullable=False, server_default="105")
    component_silo_e_name = Column(String(64), nullable=True)
    consumption_silo_e = Column(Float, nullable=True)
    silo_f = Column(Integer, nullable=False, server_default="106")
    component_silo_f_name = Column(String(64), nullable=True)
    consumption_silo_f = Column(Float, nullable=True)
    silo_g = Column(Integer, nullable=False, server_default="107")
    component_silo_g_name = Column(String(64), nullable=True)
    consumption_silo_g = Column(Float, nullable=True)
    silo_h = Column(Integer, nullable=False, server_default="108")
    component_silo_h_name = Column(String(64), nullable=True)
    consumption_silo_h = Column(Float, nullable=True)
    silo_i = Column(Integer, nullable=False, server_default="109")
    component_silo_i_name = Column(String(64), nullable=True)
    consumption_silo_i = Column(Float, nullable=True)
    silo_j = Column(Integer, nullable=False, server_default="110")
    component_silo_j_name = Column(String(64), nullable=True)
    consumption_silo_j = Column(Float, nullable=True)
    silo_k = Column(Integer, nullable=False, server_default="111")
    component_silo_k_name = Column(String(64), nullable=True)
    consumption_silo_k = Column(Float, nullable=True)
    silo_l = Column(Integer, nullable=False, server_default="112")
    component_silo_l_name = Column(String(64), nullable=True)
    consumption_silo_l = Column(Float, nullable=True)
    silo_m = Column(Integer, nullable=False, server_default="113")
    component_silo_m_name = Column(String(64), nullable=True)
    consumption_silo_m = Column(Float, nullable=True)

    status_manufacturing = Column(Boolean, nullable=False, server_default="false")
    status_operation = Column(Boolean, nullable=False, server_default="false")
    actual_weight_quantity_finished_goods = Column(Numeric(18, 3), nullable=True)

