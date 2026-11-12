from sqlalchemy import String,Text,JSON,ForeignKey,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class CheckItem(RecordMixin,Base):
 __tablename__="check_items"
 __table_args__=(UniqueConstraint("review_id","document_id","source",name="uq_check_review_document_source"),)
 review_id:Mapped[str]=mapped_column(ForeignKey("reviews.id",ondelete="CASCADE"),index=True)
 document_id:Mapped[str]=mapped_column(String(80),index=True)
 result:Mapped[str]=mapped_column(String(20))
 # active 有效结论；superseded 冲突裁决后被否定的原始条目，仍保留留痕
 status:Mapped[str]=mapped_column(String(20),default="active")
 source:Mapped[str]=mapped_column(String(160),default="")
 note:Mapped[str]=mapped_column(Text,default="")
 raw_payload:Mapped[dict]=mapped_column(JSON,default=dict)
