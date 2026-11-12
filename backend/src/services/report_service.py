import csv
import io
from uuid import uuid4
from sqlalchemy import select
from fastapi import HTTPException
from ..models.review import ReviewDecision
from ..models.check import CheckItem
from ..models.draw import SampleDraw
from ..models.run import AllocationRun
from ..models.report import Report
from ..models.common import now
from ..services.confidence import upper_error_bound


def measured_summary(db, review, draw):
    """按风险层汇总实检差错数，并计算 95% 单侧差错总量置信上界（不沿用预估率）。"""
    items = list(db.scalars(select(CheckItem).where(
        CheckItem.review_id == review.id,
        CheckItem.status == "active",
    )).all())
    # 批准闸门已保证：每个文档恰有一个 active 结论（冲突经裁决后其余条目为 superseded）
    final_result = {i.document_id: i.result for i in items}
    run = db.get(AllocationRun, draw.run_id)
    strata_meta = {s["stratum"]: s for s in run.result["strata"]}
    layers = {}
    for row in draw.manifest:
        layer = layers.setdefault(row["stratum"], {"stratum": row["stratum"], "N": 0, "n": 0, "d": 0})
        layer["N"] = strata_meta[row["stratum"]]["N"]
        layer["n"] += 1
        if final_result.get(row["document_id"]) == "error":
            layer["d"] += 1
    out = []
    for key in sorted(layers):
        layer = layers[key]
        upper = upper_error_bound(layer["N"], layer["n"], layer["d"])
        out.append({
            **layer,
            "upper_95": upper,
            "observed_rate": round(layer["d"] / layer["n"], 6) if layer["n"] else 0.0,
            "error_rate_upper": round(upper / layer["N"], 6),
            "confidence_level": 0.95,
            "estimated_D_assumption_only": strata_meta[key]["D"],
        })
    return out, run


def create(db, body):
    review = db.get(ReviewDecision, body.review_id)
    if review is None or review.state not in ("approved", "sealed"):
        raise HTTPException(409, "报告必须关联已批准复核")
    existing = db.scalar(select(Report).where(Report.review_id == body.review_id))
    if existing:
        return existing
    draw = db.get(SampleDraw, review.draw_id)
    layers, run = measured_summary(db, review, draw)
    # 批准后封存复核证据：逐份结论、来源、冲突裁决留痕与统计口径写入不可变快照
    items = list(db.scalars(select(CheckItem).where(CheckItem.review_id == review.id)).all())
    evidence = {
        "sealed_at": now().isoformat() + "Z",
        "reviewer": review.reviewer,
        "checks": [
            {"document_id": i.document_id, "result": i.result, "status": i.status,
             "source": i.source, "note": i.note,
             "created_at": i.created_at.isoformat() + "Z"}
            for i in sorted(items, key=lambda x: (x.document_id, x.created_at))
        ],
        "layers": layers,
        "method": "有限总体无放回抽样，Clopper-Pearson 型超几何单侧 95% 置信上界；仅依据实测差错，不沿用预估差错率。",
    }
    review.state = "sealed"
    review.sealed_at = evidence["sealed_at"]
    review.sealed_evidence = evidence
    row = Report(
        id=str(uuid4()), review_id=review.id, title=body.title,
        snapshot={
            "manifest": draw.manifest, "allocation": run.result,
            "action": review.action, "reviewer": review.reviewer,
            "measured": layers, "sealed_evidence": evidence,
        },
    )
    db.add(row)
    db.commit()
    return row


def export(row):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "position", "document_id", "lot_name", "stratum", "stratum_N",
        "checked_n", "observed_errors_d", "upper_95_total_errors",
        "observed_rate", "upper_95_error_rate",
        "assumed_D_design_only", "stratum_quota",
        "detection_probability_design", "miss_probability_design",
        "guaranteed_detection_design",
    ])
    layers = {s["stratum"]: s for s in row.snapshot["measured"]}
    design = {s["stratum"]: s for s in row.snapshot["allocation"]["strata"]}
    # 裁决优先，重算最终判定（仅 active 条目；superseded 保留在来源列留痕）
    final = {}
    for c in row.snapshot["sealed_evidence"]["checks"]:
        if c["status"] != "active":
            continue
        if c["source"] == "adjudication":
            final[c["document_id"]] = c["result"]
        else:
            final.setdefault(c["document_id"], c["result"])
    for r in row.snapshot["manifest"]:
        m, d = layers[r["stratum"]], design[r["stratum"]]
        writer.writerow([
            r["position"], r["document_id"], r["lot_name"], r["stratum"], m["N"],
            m["n"], m["d"], m["upper_95"], m["observed_rate"], m["error_rate_upper"],
            m["estimated_D_assumption_only"], d["quota"],
            d["detection_probability"], d["miss_probability"], d["guaranteed"],
        ])
    writer.writerow([])
    writer.writerow(["风险层汇总（实测口径，95%单侧置信上界，零差错照算）"])
    writer.writerow(["stratum", "N", "checked_n", "observed_errors_d",
                     "upper_95_total_errors", "observed_rate", "upper_95_error_rate"])
    for m in row.snapshot["measured"]:
        writer.writerow([m["stratum"], m["N"], m["n"], m["d"], m["upper_95"],
                         m["observed_rate"], m["error_rate_upper"]])
    writer.writerow([])
    writer.writerow(["逐份封存复核证据（含来源与管理员裁决）"])
    writer.writerow(["document_id", "final_result", "all_sources"])
    sources = {}
    for c in row.snapshot["sealed_evidence"]["checks"]:
        tag = c["source"] + ":" + c["result"]
        if c["status"] == "superseded":
            tag += "(superseded)"
        sources.setdefault(c["document_id"], []).append(tag)
    for doc_id in sorted(sources):
        writer.writerow([doc_id, final[doc_id], " | ".join(sources[doc_id])])
    return "﻿" + out.getvalue()
