<script setup lang="ts">
import {computed, ref} from 'vue';
import type {Entity,Coverage,CheckResult,DocumentRow} from '../types/domain';
import {mergeChecks} from '../api/reviews';
import {useTask} from '../hooks/useTask';
import Notice from './common/Notice.vue';
const props=defineProps<{review:Entity;coverage:Coverage;manifest:DocumentRow[];locked:boolean}>();
const emit=defineEmits<{changed:[]}>();
const source=ref(localStorage.getItem('check-source')||'reviewer-a');
const note=ref('');
const verdict=ref<Record<string,CheckResult>>({});
const pasteText=ref('');
const showPaste=ref(false);
const search=ref('');
const onlyMissing=ref(true);
const {error,busy,act}=useTask();
const missingSet=computed(()=>new Set(props.coverage.missing_document_ids));
const errorSet=computed(()=>new Set(props.coverage.error_document_ids));
const conflictSet=computed(()=>new Set(props.coverage.conflicts.map(c=>c.document_id)));
const adjudicatedSet=computed(()=>new Set(props.coverage.adjudicated_document_ids));
function statusOf(doc:string){
 if(conflictSet.value.has(doc))return {key:'conflict',text:'冲突待裁'};
 if(missingSet.value.has(doc))return {key:'missing',text:'漏检'};
 if(adjudicatedSet.value.has(doc))return {key:'adjudicated',text:'已裁决'};
 if(errorSet.value.has(doc))return {key:'error',text:'差错'};
 return {key:'qualified',text:'合格'};
}
const rows=computed(()=>{
 const q=search.value.trim().toLowerCase();
 return props.manifest.filter(r=>{
  if(onlyMissing.value&&!missingSet.value.has(r.document_id))return false;
  return !q||r.document_id.toLowerCase().includes(q);
 });
});
function setResult(doc:string,r:CheckResult){verdict.value[doc]=r}
function toggleAll(r:CheckResult){
 props.coverage.missing_document_ids.forEach(d=>{verdict.value[d]=r});
}
const pending=computed(()=>Object.entries(verdict.value).filter(([,r])=>!!r).map(([document_id,result])=>({document_id,result,note:note.value||undefined})));
function submit(){
 if(!source.value.trim())return;
 localStorage.setItem('check-source',source.value);
 act(async()=>{
  await mergeChecks(props.review.id,{source:source.value.trim(),entries:pending.value});
  verdict.value={};note.value='';emit('changed');
 });
}
function parsePaste(){
 try{
  const lines=pasteText.value.split(/\r?\n/).map(l=>l.trim()).filter(Boolean);
  const entries:any[]=[];
  for(const line of lines){
   const [doc,raw]=line.split(/[,\t;，]/).map(s=>s?.trim());
   if(!doc||!raw)continue;
   const r=raw.includes('差')||raw.toLowerCase()==='error'||raw==='1'?'error':'qualified';
   entries.push({document_id:doc,result:r});
  }
  if(!entries.length)throw new Error('未解析到有效行，格式：文档编号,合格/差错');
  act(async()=>{
   await mergeChecks(props.review.id,{source:source.value.trim()||'offline-import',entries});
   pasteText.value='';showPaste.value=false;emit('changed');
  });
 }catch(e:any){error.value=e.message}
}
</script>
<template>
 <div class="check-workbench">
  <Notice :message="error"/>
  <div v-if="locked" class="notice">该复核已批准封存，检查结果不可变更；逐份证据见归档快照。</div>
  <template v-else>
   <div class="workbench-controls">
    <label>报送来源（离线设备/复核员标识）<input v-model="source" placeholder="如 reviewer-a / 巡检平板03"></label>
    <div class="bulk-actions">
     <button type="button" class="secondary" @click="toggleAll('qualified')">漏检项一键合格</button>
     <button type="button" class="secondary" @click="toggleAll('error')">漏检项一键差错</button>
     <button type="button" class="secondary" @click="showPaste=!showPaste">{{showPaste?'收起粘贴导入':'粘贴离线结果导入'}}</button>
    </div>
   </div>
   <div v-if="showPaste" class="paste-box">
    <p class="method-note">每行一份，格式「文档编号,合格|差错」，逗号/制表符/分号均可；同来源重复报送不增计。</p>
    <textarea v-model="pasteText" rows="6" placeholder="GL-HIGH-1-00001,合格&#10;GL-HIGH-1-00002,差错"></textarea>
    <button type="button" @click="parsePaste" :disabled="busy">解析并合并</button>
   </div>
   <div class="check-filter">
    <label class="inline">查找文档<input v-model="search" placeholder="输入文档编号"></label>
    <label class="checkbox-label"><input type="checkbox" v-model="onlyMissing">仅看漏检（{{coverage.missing_total}}）</label>
   </div>
   <div class="table-wrap check-table">
    <table>
     <thead><tr><th>文档编号</th><th>当前状态</th><th colspan="2">本次登记</th></tr></thead>
     <tbody>
      <tr v-for="r in rows" :key="r.document_id">
       <td class="document-id">{{r.document_id}}</td>
       <td><span :class="['tag','tag-'+statusOf(r.document_id).key]">{{statusOf(r.document_id).text}}</span></td>
       <td><button type="button" :class="{secondary:verdict[r.document_id]!=='qualified'}" @click="setResult(r.document_id,'qualified')">合格</button></td>
       <td><button type="button" :class="{secondary:verdict[r.document_id]!=='error'}" @click="setResult(r.document_id,'error')">差错</button></td>
      </tr>
      <tr v-if="!rows.length"><td colspan="4" class="all-done">没有匹配文档。</td></tr>
     </tbody>
    </table>
   </div>
   <label>本批备注（可选）<textarea v-model="note" rows="3" placeholder="离线复核环境、批次说明"></textarea></label>
   <div class="submit-line">
    <button @click="submit" :disabled="busy||!pending.length">合并 {{pending.length}} 份登记结果</button>
    <small>同一来源重复报送幂等不增计；与其他来源结论矛盾时自动保留冲突，交管理员裁决。</small>
   </div>
  </template>
 </div>
</template>
