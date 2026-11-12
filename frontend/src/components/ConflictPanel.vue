<script setup lang="ts">
import {ref} from 'vue';
import type {Conflict,CheckResult} from '../types/domain';
import {resolveConflict} from '../api/reviews';
import {useTask} from '../hooks/useTask';
import Notice from './common/Notice.vue';
const props=defineProps<{reviewId:string;conflicts:Conflict[];locked:boolean}>();
const emit=defineEmits<{changed:[]}>();
const {error,busy,act}=useTask();
const notes=ref<Record<string,string>>({});
function adjudicate(doc:string,result:CheckResult){
 act(async()=>{
  await resolveConflict(props.reviewId,{document_id:doc,result,note:notes.value[doc]||''});
  emit('changed');
 });
}
const label:Record<CheckResult,string>={qualified:'合格',error:'差错'};
</script>
<template>
 <section class="conflict-panel">
  <h3>矛盾结论待裁决 <span class="conflict-count">{{conflicts.length}}</span></h3>
  <Notice :message="error"/>
  <p v-if="!conflicts.length" class="method-note">当前无未裁决冲突。同时报送的矛盾结论会在此保留全部来源记录，由管理员裁决后才可批准。</p>
  <article v-for="c in conflicts" :key="c.document_id" class="conflict-card">
   <p class="document-id">{{c.document_id}}</p>
   <ul>
    <li v-for="e in c.entries" :key="e.source+e.created_at">
     <b>{{e.source}}</b> → <span :class="e.result">{{label[e.result as CheckResult]}}</span>
     <small v-if="e.note">（{{e.note}}）</small>
    </li>
   </ul>
   <template v-if="!locked">
    <input v-model="notes[c.document_id]" placeholder="裁决依据（可选）">
    <div class="actions">
     <button :disabled="busy" @click="adjudicate(c.document_id,'qualified')">裁决为合格</button>
     <button class="secondary" :disabled="busy" @click="adjudicate(c.document_id,'error')">裁决为差错</button>
    </div>
   </template>
   <p v-else class="method-note">已封存，裁决记录见归档证据。</p>
  </article>
 </section>
</template>
