from sqlalchemy import String,Text,JSON,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class ReviewDecision(RecordMixin,Base):
 __tablename__="reviews"
 draw_id:Mapped[str]=mapped_column(ForeignKey("draws.id"))
 action:Mapped[str]=mapped_column(Text)
 # submitted 已提交待批 / approved 已批准封存 / conflicted 存在冲突待裁决 / sealed 证据已封存
 state:Mapped[str]=mapped_column(String(20),default="submitted")
 reviewer:Mapped[str]=mapped_column(String(160),default="")
 sealed_at:Mapped[str]=mapped_column(String(40),default="")
 sealed_evidence:Mapped[dict]=mapped_column(JSON,default=dict)
