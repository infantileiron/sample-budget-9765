<script setup lang="ts">
import type {MeasuredLayer} from '../types/domain';
import {strataLabels} from '../constants/enums';
defineProps<{rows:MeasuredLayer[]}>();
const pct=(v:number)=>(v*100).toFixed(2)+'%';
</script>
<template>
 <div class="table-wrap">
  <table>
   <thead>
    <tr><th>风险层</th><th>层总体 N</th><th>实检 n</th><th>实检差错 d</th><th>实测差错率</th><th>95% 单侧差错总量上界（份）</th><th>上界对应差错率</th><th>设计假设 D（仅留档）</th></tr>
   </thead>
   <tbody>
    <tr v-for="r in rows" :key="r.stratum">
     <td>{{strataLabels[r.stratum]}}</td>
     <td>{{r.N}}</td>
     <td>{{r.n}}</td>
     <td><strong>{{r.d}}</strong></td>
     <td>{{pct(r.observed_rate)}}</td>
     <td class="upper-bound">{{r.upper_95}}</td>
     <td>{{pct(r.error_rate_upper)}}</td>
     <td class="muted-cell">{{r.estimated_D_assumption_only}}</td>
    </tr>
   </tbody>
  </table>
  <p class="method-note">有限总体无放回抽样，Clopper–Pearson 型超几何单侧 95% 置信上界；仅依据实测差错数计算，零差错同样照算，不沿用抽样设计阶段的预估差错率。</p>
 </div>
</template>
