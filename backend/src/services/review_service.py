from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from ..models.review import ReviewDecision
from ..models.check import CheckItem
from ..models.draw import SampleDraw


def create(db, body):
    if not db.get(SampleDraw, body.draw_id):
        raise HTTPException(409, "请选择已生成的实际抽样清单")
    existing = db.scalar(select(ReviewDecision).where(ReviewDecision.draw_id == body.draw_id))
    if existing:
        if existing.state in ("approved", "sealed"):
            raise HTTPException(409, "该清单复核已批准封存，不可再登记结果")
        return existing
    row = ReviewDecision(id=str(uuid4()), **body.model_dump(), state="submitted", reviewer="")
    db.add(row)
    db.commit()
    return row


def _active_items(db, review_id):
    return list(db.scalars(select(CheckItem).where(
        CheckItem.review_id == review_id,
        CheckItem.status == "active",
    )).all())


def coverage(db, review):
    """逐份登记进度与冲突清单（仅统计 active 条目；superseded 为裁决留痕）。"""
    draw = db.get(SampleDraw, review.draw_id)
    manifest_ids = [r["document_id"] for r in draw.manifest]
    by_doc = {}
    for item in _active_items(db, review.id):
        by_doc.setdefault(item.document_id, []).append(item)
    all_items = list(db.scalars(select(CheckItem).where(
        CheckItem.review_id == review.id)).all())
    checked, errors, conflicts = [], [], []
    for doc_id in manifest_ids:
        docs = by_doc.get(doc_id, [])
        results = {i.result for i in docs}
        if not docs:
            continue
        checked.append(doc_id)
        if len(results) > 1:
            conflicts.append({
                "document_id": doc_id,
                "results": sorted(results),
                "sources": sorted({i.source for i in docs}),
                "entries": [
                    {"source": i.source, "result": i.result, "note": i.note,
                     "created_at": i.created_at.isoformat() + "Z"}
                    for i in sorted(docs, key=lambda x: x.created_at)
                ],
            })
        elif "error" in results:
            errors.append(doc_id)
    history = {}
    for item in all_items:
        history.setdefault(item.document_id, []).append(item)
    return {
        "manifest_total": len(manifest_ids),
        "checked_total": len(checked),
        "missing_total": len(manifest_ids) - len(checked),
        "error_total": len(errors),
        "conflict_total": len(conflicts),
        "conflicts": conflicts,
        "missing_document_ids": [d for d in manifest_ids if d not in set(checked)],
        "error_document_ids": errors,
        "adjudicated_document_ids": sorted(
            d for d, group in history.items()
            if any(i.source == "adjudication" for i in group)
        ),
    }


def merge_batch(db, review, body, user):
    """离线结果合并。

    - 仅登记清单内文档，清单外拒绝整批；
    - 同一 (review, document, source) 重复报送不增计（幂等覆盖同来源最新结论）；
    - 不同来源对同一文档结论矛盾时保留全部条目，标记冲突，交管理员裁决；
    - 已批准/封存的复核拒绝再写入。
    """
    if review.state in ("approved", "sealed"):
        raise HTTPException(409, "复核已批准封存，结果不可变更")
    draw = db.get(SampleDraw, review.draw_id)
    manifest_ids = {r["document_id"] for r in draw.manifest}
    unknown = sorted({e.document_id for e in body.entries} - manifest_ids)
    if unknown:
        raise HTTPException(422, "存在不属于本抽样清单的文档编号：" + "、".join(unknown[:5]))
    accepted = duplicated = 0
    for entry in body.entries:
        same = db.scalar(select(CheckItem).where(
            CheckItem.review_id == review.id,
            CheckItem.document_id == entry.document_id,
            CheckItem.source == body.source,
        ))
        if same is not None:
            # 重复报送：不新增条目；同来源结论/备注以最新报送覆盖，仍不增计
            same.result = entry.result
            same.note = entry.note
            same.status = "active"
            same.raw_payload = entry.model_dump()
            duplicated += 1
            continue
        db.add(CheckItem(
            id=str(uuid4()), review_id=review.id, document_id=entry.document_id,
            result=entry.result, status="active", source=body.source,
            note=entry.note, raw_payload=entry.model_dump(),
        ))
        accepted += 1
    review.state = "submitted"
    db.commit()
    return {"accepted": accepted, "duplicated": duplicated, "source": body.source,
            **coverage(db, review)}


def resolve_conflict(db, review, body, user):
    """管理员裁决矛盾文档：写入裁决条目，被否定的原始 active 条目标记 superseded 留痕。"""
    if review.state in ("approved", "sealed"):
        raise HTTPException(409, "复核已批准封存，冲突不可再裁决")
    active = [i for i in _active_items(db, review.id) if i.document_id == body.document_id]
    if not active:
        raise HTTPException(404, "该文档尚无检查记录")
    if len({i.result for i in active}) < 2:
        raise HTTPException(409, "该文档结论一致，不存在待裁决冲突")
    adjudicated = db.scalar(select(CheckItem).where(
        CheckItem.review_id == review.id,
        CheckItem.document_id == body.document_id,
        CheckItem.source == "adjudication",
    ))
    # 重新裁决：先把此前被 supersede 的条目恢复，再按本次结论重新标记
    prior = list(db.scalars(select(CheckItem).where(
        CheckItem.review_id == review.id,
        CheckItem.document_id == body.document_id,
        CheckItem.source != "adjudication",
    )).all())
    for item in prior:
        item.status = "active"
    for item in prior:
        if item.result != body.result:
            item.status = "superseded"
    if adjudicated is None:
        db.add(CheckItem(
            id=str(uuid4()), review_id=review.id, document_id=body.document_id,
            result=body.result, status="active", source="adjudication",
            note=("管理员裁决：" + body.note)[:2000], raw_payload=body.model_dump(),
        ))
    else:
        adjudicated.result = body.result
        adjudicated.status = "active"
        adjudicated.note = ("管理员裁决：" + body.note)[:2000]
    db.commit()
    return coverage(db, review)


def approve(db, row, user):
    """批准闸门：漏检或冲突未清的清单不能批准。"""
    if row.state in ("approved", "sealed"):
        raise HTTPException(409, "复核已处理")
    summary = coverage(db, row)
    if summary["missing_total"]:
        raise HTTPException(409, f"仍有 {summary['missing_total']} 份档案未登记检查结果，不能批准")
    if summary["conflict_total"]:
        raise HTTPException(409, f"仍有 {summary['conflict_total']} 份档案结论冲突未裁决，不能批准")
    row.state = "approved"
    row.reviewer = user.email
    db.commit()
    return row
