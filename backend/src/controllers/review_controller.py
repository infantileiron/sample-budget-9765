from ..services import review_service
from ..models.review import ReviewDecision
from ..models.common import serialize
from .common import listing,require
def list_all(db):return listing(db,ReviewDecision)
def detail(db,ident):
 row=require(db,ReviewDecision,ident)
 payload=serialize(row)
 payload["coverage"]=review_service.coverage(db,row)
 return payload
def create(db,body):return serialize(review_service.create(db,body))
def coverage(db,ident):
 row=require(db,ReviewDecision,ident)
 return review_service.coverage(db,row)
def merge(db,ident,body,user):
 row=require(db,ReviewDecision,ident)
 return review_service.merge_batch(db,row,body,user)
def resolve(db,ident,body,user):
 row=require(db,ReviewDecision,ident)
 return review_service.resolve_conflict(db,row,body,user)
