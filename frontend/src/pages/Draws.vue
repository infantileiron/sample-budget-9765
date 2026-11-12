<script setup lang="ts">
import {ref,computed,onMounted,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {draws} from '../stores/draws';
import {reviews} from '../stores/reviews';
import {canWrite} from '../stores/auth';
import {useTask} from '../hooks/useTask';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import EmptyState from '../components/common/EmptyState.vue';
import ManifestTable from '../components/ManifestTable.vue';
const route=useRoute(),router=useRouter(),selected=ref(String(route.query.draw||'')),search=ref(''),action=ref('按固定seed清单逐份复核，逐份登记合格或差错；离线结果按来源合并，漏检或冲突未清不批准。'),notice=ref('');
watch(()=>route.query.draw,value=>{selected.value=String(value||draws.items.value[0]?.id||'')});
const {error,busy,act}=useTask();
onMounted(async()=>{await Promise.all([draws.load(),reviews.load()]);if(!selected.value)selected.value=draws.items.value[0]?.id||''});
const draw=computed(()=>draws.items.value.find(r=>r.id===selected.value));
const reviewOf=computed(()=>reviews.items.value.find(r=>r.draw_id===selected.value));
const filtered=computed(()=>draw.value?.manifest.filter((r:any)=>r.document_id.toLowerCase().includes(search.value.toLowerCase()))||[]);
function submit(){act(async()=>{const r=await reviews.create({draw_id:selected.value,action:action.value});notice.value='复核单已建立，请在复核归档页逐份登记检查结果。';setTimeout(()=>router.push('/reports'),800);return r})}
</script>
<template>
 <PageHeading index="04 / 抽样清单" title="抽到哪一份，就复核哪一份。" note="后台保存固定seed抽出的具体文档编号。清单不会随刷新重抽，层内无放回且全局编号不重复；每份档案必须逐份登记合格或差错后才可批准。"/>
 <Notice :message="error||draws.error.value"/>
 <EmptyState v-if="!draws.items.value.length" text="还没有可行抽样。先完成预算计算；不可行计划不会生成文档清单。"/>
 <div v-if="draw" class="draw-layout">
  <section>
   <div class="draw-controls">
    <label>抽样批次<select v-model="selected"><option v-for="r in draws.items.value" :key="r.id" :value="r.id">{{r.id.slice(0,8)}} · {{r.manifest.length}}份</option></select></label>
    <label>查找文档编号<input v-model="search" placeholder="如 GL-HIGH"></label>
   </div>
   <p class="manifest-note">共 {{draw.manifest.length}} 份 · seed {{draw.seed}} · 当前匹配 {{filtered.length}} 份</p>
   <ManifestTable :rows="filtered.slice(0,80)"/>
   <p class="method-note">页面预览前80条匹配结果，完整清单与逐份复核结论在批准后CSV中下载。</p>
  </section>
  <form v-if="canWrite()" class="editor-panel" @submit.prevent="submit">
   <p class="eyebrow">HUMAN REVIEW</p>
   <h2>建立复核单</h2>
   <p class="method-note">说明不能代替逐份检查。建立复核单后，在「复核归档」页按文档逐份登记合格/差错，并支持离线结果合并与冲突裁决。</p>
   <label>复核说明<textarea v-model="action" required minlength="8" rows="6"></textarea></label>
   <button v-if="!reviewOf" :disabled="busy">建立复核单并去登记</button>
   <button type="button" class="secondary" v-else @click="router.push('/reports')">该清单已有复核单，前往登记 →</button>
   <p class="success" v-if="notice">{{notice}}</p>
  </form>
 </div>
</template>
