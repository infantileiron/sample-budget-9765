from typing import Literal
from pydantic import BaseModel,Field

class ReviewCreate(BaseModel):
 draw_id:str
 action:str=Field(min_length=8,max_length=3000)

class CheckEntry(BaseModel):
 document_id:str=Field(min_length=1,max_length=80)
 result:Literal["qualified","error"]
 source:str=Field(default="",max_length=160)
 note:str=Field(default="",max_length=2000)

class CheckBatch(BaseModel):
 # 离线结果合并：同一来源可重复报送，重复文档不增计；不同来源矛盾结论保留为冲突
 source:str=Field(min_length=1,max_length=160)
 entries:list[CheckEntry]=Field(min_length=1,max_length=5000)

class ConflictResolve(BaseModel):
 document_id:str=Field(min_length=1,max_length=80)
 result:Literal["qualified","error"]
 note:str=Field(default="",max_length=2000)
