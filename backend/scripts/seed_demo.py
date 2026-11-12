import json
from sqlalchemy import select,func
from src.config.database import initialize,Session
from src.models import ArchiveLot,SamplingPlan,AllocationRun,SampleDraw,ReviewDecision,CheckItem,Report,User
from src.utils.security import hash_password
from src.services.run_service import compute
from src.services.review_service import coverage

def seed():
 initialize()
 with Session() as db:
  for role in ["admin","analyst","viewer"]:
   email=role+"@sample.demo"
   if not db.scalar(select(User).where(User.email==email)):db.add(User(id="user-"+role,email=email,role=role,password_hash=hash_password("ArchiveDemo2026!")))
  ids=[]
  for layer,p,label in [("low",.01,"常规"),("moderate",.03,"关注"),("high",.06,"高风险"),("critical",.12,"重点")]:
   for i,N in enumerate([100,150,200]):
    ident=f"demo-{layer}-{i}";ids.append(ident)
    if not db.get(ArchiveLot,ident):db.add(ArchiveLot(id=ident,name=f"{label}档案批次 {i+1}",stratum=layer,size=N,estimated_error_rate=p,doc_prefix=f"GL-{layer.upper()}-{i+1}",description="模拟数字化验收批次；预估差错率用于抽样设计，不是实际已测差错率"))
  db.commit()
  if not db.get(SamplingPlan,"demo-plan"):db.add(SamplingPlan(id="demo-plan",name="十一月档案四层复核",lot_ids=ids,target_detection=.95,budget=480,seed=20261112))
  db.commit()
  if not db.get(AllocationRun,"demo-run"):db.add(AllocationRun(id="demo-run",plan_id="demo-plan",status="queued",result={},error=""));db.commit();compute(db,"demo-run")
  draw=db.scalar(select(SampleDraw).where(SampleDraw.run_id=="demo-run"))
  if draw and not db.get(ReviewDecision,"demo-review"):
   review=ReviewDecision(id="demo-review",draw_id=draw.id,action="逐份登记离线复核结果并按层汇总实测差错；检出率设计值依赖预估差错数假设，置信上界仅依据实测数据。",state="submitted",reviewer="")
   db.add(review);db.commit()
   # 离线两批报送：复核员A全量初判；复核员B对其中两份复查，制造一处矛盾后由管理员裁决
   error_docs={row["document_id"] for idx,row in enumerate(draw.manifest) if idx%37==0}
   for row in draw.manifest:
    result="error" if row["document_id"] in error_docs else "qualified"
    db.add(CheckItem(id="check-a-"+str(row["position"]),review_id=review.id,document_id=row["document_id"],result=result,source="reviewer-a",note="离线初检",raw_payload={}))
   conflict_doc=draw.manifest[5]["document_id"]
   conflict_result="error" if conflict_doc not in error_docs else "qualified"
   db.add(CheckItem(id="check-b-conflict",review_id=review.id,document_id=conflict_doc,result=conflict_result,source="reviewer-b",note="离线复查结论不一致，保留冲突待裁决",raw_payload={}))
   db.commit()
   summary=coverage(db,review)
   # 管理员裁决冲突文档（采用复核员A口径），随后全部清单满足批准闸门
   target=next(c for c in summary["conflicts"] if c["document_id"]==conflict_doc)
   adj_result=next(e["result"] for e in target["entries"] if e["source"]=="reviewer-a")
   from src.schemas.review import ConflictResolve
   from src.services.review_service import resolve_conflict
   class _Admin:email="admin@sample.demo";role="admin"
   resolve_conflict(db,review,ConflictResolve(document_id=conflict_doc,result=adj_result,note="采纳复核员A初检结论"),_Admin())
  review=db.get(ReviewDecision,"demo-review")
  if draw and review and review.state!="sealed" and not db.get(Report,"demo-report"):
   review.state="approved";review.reviewer="admin@sample.demo";db.commit()
   from src.services.report_service import create as create_report
   from src.schemas.report import ReportCreate
   create_report(db,ReportCreate(review_id="demo-review",title="四层档案复核抽样底册"))
  db.commit()
  return {cls.__tablename__:db.scalar(select(func.count()).select_from(cls)) for cls in [User,ArchiveLot,SamplingPlan,AllocationRun,SampleDraw,ReviewDecision,CheckItem,Report]}
if __name__=="__main__":print(json.dumps(seed(),ensure_ascii=False))
