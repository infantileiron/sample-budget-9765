<script setup lang="ts">
import {ref,computed,onMounted} from 'vue';
import {reviews} from '../stores/reviews';
import {reports} from '../stores/reports';
import {draws} from '../stores/draws';
import {isAdmin,canWrite} from '../stores/auth';
import {request,downloadCsv} from '../api/client';
import {useTask} from '../hooks/useTask';
import PageHeading from '../components/common/PageHeading.vue';
import StatusPill from '../components/common/StatusPill.vue';
import Notice from '../components/common/Notice.vue';
import EmptyState from '../components/common/EmptyState.vue';
import CheckWorkbench from '../components/CheckWorkbench.vue';
import ConflictPanel from '../components/ConflictPanel.vue';
import MeasuredTable from '../components/MeasuredTable.vue';
import type {Entity,Coverage} from '../types/domain';

const selected=ref('');
const coverages=ref<Record<string,Coverage>>({});
const {error,busy,act}=useTask();
onMounted(async()=>{
 await Promise.all([reviews.load(),reports.load(),draws.load()]);
 selected.value=reviews.items.value[0]?.id||'';
 await Promise.all(reviews.items.value.map(r=>loadCoverage(r.id)));
});
const review=computed(()=>reviews.items.value.find(r=>r.id===selected.value));
const coverage=computed<Coverage|undefined>(()=>review.value?coverages.value[review.value.id]:undefined);
const locked=computed(()=>!!review.value&&['approved','sealed'].includes(review.value.state));
const reportOf=(id:string)=>reports.items.value.find(r=>r.review_id===id);
const currentReport=computed(()=>review.value?reportOf(review.value.id):undefined);
const drawOf=(drawId:string)=>draws.items.value.find(d=>d.id===drawId);

async function loadCoverage(id:string){
 try{coverages.value[id]=await request('/reviews/'+id+'/coverage')}catch(e:any){/* 清单可能已删除 */}
}
function pick(id:string){selected.value=id;if(!coverages.value[id])loadCoverage(id)}
async function refresh(){await reviews.load();if(selected.value)await loadCoverage(selected.value)}
function approve(id:string){act(async()=>{await request('/reviews/'+id+'/approve','POST');await refresh()})}
function publish(id:string){act(async()=>{await reports.create({review_id:id,title:'档案复核归档底册 '+new Date().toLocaleDateString()});await reports.load()})}
function download(id:string){act(()=>downloadCsv(id))}
const pct=(c:Coverage)=>c.manifest_total?Math.round(c.checked_total/c.manifest_total*100):0;
</script>

<template>
 <PageHeading index="05 / 复核归档" title="逐份登记合格或差错，漏检冲突不清不批准。" note="离线结果按来源合并，重复报送不增计；同时报送的矛盾结论保留全部记录，由管理员裁决。批准后封存逐份复核证据，报告按风险层给出实测差错数与 95% 单侧置信上界。"/>
 <Notice :message="error"/>
 <EmptyState v-if="!reviews.items.value.length" text="还没有复核单。先在抽样清单页提交复核依据。"/>
 <div v-if="reviews.items.value.length" class="review-layout">
  <section class="review-list">
   <h2>复核清单</h2>
   <article v-for="r in reviews.items.value" :key="r.id" :class="['review-row',{active:r.id===selected}]" @click="pick(r.id)">
    <div class="review-head"><StatusPill :status="r.state"/><small>{{r.id.slice(0,8)}}</small></div>
    <p>{{r.action}}</p>
    <template v-if="coverages[r.id]">
     <div class="progress-track"><i :style="{width:pct(coverages[r.id])+'%'}"></i></div>
     <div class="coverage-meta">
      <span>已检 {{coverages[r.id].checked_total}}/{{coverages[r.id].manifest_total}}</span>
      <span>差错 {{coverages[r.id].error_total}}</span>
      <span :class="{warn:coverages[r.id].conflict_total}">冲突 {{coverages[r.id].conflict_total}}</span>
      <span v-if="coverages[r.id].missing_total" class="warn">漏检 {{coverages[r.id].missing_total}}</span>
     </div>
    </template>
   </article>
  </section>

  <section v-if="review&&coverage" class="review-detail">
   <div class="detail-head">
    <h2>复核单 {{review.id.slice(0,8)}} · 清单 {{drawOf(review.draw_id)?.manifest.length||'—'}} 份</h2>
    <StatusPill :status="review.state"/>
   </div>

   <div class="gate-summary">
    <div><strong>{{coverage.checked_total}}/{{coverage.manifest_total}}</strong><span>逐份已登记</span></div>
    <div><strong>{{coverage.error_total}}</strong><span>实测差错</span></div>
    <div :class="{warn:coverage.conflict_total}"><strong>{{coverage.conflict_total}}</strong><span>待裁决冲突</span></div>
    <div :class="{warn:coverage.missing_total}"><strong>{{coverage.missing_total}}</strong><span>漏检未登记</span></div>
   </div>

   <ConflictPanel v-if="isAdmin()" :review-id="review.id" :conflicts="coverage.conflicts" :locked="locked" @changed="refresh"/>

   <CheckWorkbench v-if="canWrite()" :review="review" :coverage="coverage" :manifest="drawOf(review.draw_id)?.manifest||[]" :locked="locked" @changed="refresh"/>

   <div v-if="isAdmin()" class="approve-box">
    <template v-if="review.state==='submitted'">
     <p v-if="coverage.missing_total||coverage.conflict_total" class="notice">
      批准闸门未通过：{{coverage.missing_total?`漏检 ${coverage.missing_total} 份；`:''}}{{coverage.conflict_total?`冲突 ${coverage.conflict_total} 份未裁决；`:''}}清结后才可批准。
     </p>
     <button :disabled="busy||!!coverage.missing_total||!!coverage.conflict_total" @click="approve(review.id)">批准复核并锁定结果</button>
    </template>
    <template v-else>
     <p class="success">已由 {{review.reviewer}} 批准{{review.state==='sealed'?'，复核证据已封存':'，结果已锁定不可变更'}}。</p>
     <button v-if="review.state==='approved'&&!currentReport" :disabled="busy" @click="publish(review.id)">生成归档快照并封存证据</button>
    </template>
   </div>

   <div v-if="currentReport" class="sealed-report">
    <h3>归档报告：{{currentReport.title}}</h3>
    <MeasuredTable :rows="currentReport.snapshot.measured"/>
    <div class="actions">
     <button :disabled="busy" @click="download(currentReport.id)">下载完整 CSV（含逐份封存证据）↓</button>
    </div>
    <details class="evidence-view">
     <summary>查看封存的逐份复核证据（{{currentReport.snapshot.sealed_evidence.checks.length}} 条，含来源与裁决留痕）</summary>
     <div class="table-wrap"><table>
      <thead><tr><th>文档编号</th><th>结论</th><th>状态</th><th>来源</th><th>备注</th></tr></thead>
      <tbody><tr v-for="c in currentReport.snapshot.sealed_evidence.checks" :key="c.document_id+c.source+c.created_at">
       <td class="document-id">{{c.document_id}}</td><td>{{c.result==='error'?'差错':'合格'}}</td>
       <td>{{c.status==='superseded'?'已被裁决否定':'有效'}}</td><td>{{c.source}}</td><td>{{c.note||'—'}}</td>
      </tr></tbody>
     </table></div>
    </details>
   </div>
  </section>
 </div>
</template>
