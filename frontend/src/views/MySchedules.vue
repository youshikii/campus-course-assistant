<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>我的课表</h1>
        <p>查看自己的上课安排，选择日期可查询当天课表。</p>
      </div>
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>{{ onDate ? `${onDate} 的课表` : '每周课表' }}</h3>
        <div class="date-filter">
          <el-date-picker
            v-model="onDate"
            value-format="YYYY-MM-DD"
            placeholder="选择日期（可选）"
            clearable
            @change="load"
          /><el-button @click="reset">查看全部</el-button>
        </div>
      </div>
      <div v-if="!onDate" class="week-grid" v-loading="loading">
        <div v-for="(day, index) in weekdays" :key="day" class="week-day">
          <h4>{{ day }}</h4>
          <div
            v-for="slot in schedules.filter((item) => item.weekday === index + 1)"
            :key="slot.id"
            class="schedule-block"
          >
            <small>{{ slot.start_time.slice(0, 5) }}–{{ slot.end_time.slice(0, 5) }}</small
            ><strong>{{ slot.name }}</strong
            ><span>{{ slot.location || '地点待定' }} · {{ slot.teacher || '教师待定' }}</span
            ><small>{{ slot.start_date }} 至 {{ slot.end_date }}</small>
          </div>
          <div v-if="!schedules.some((item) => item.weekday === index + 1)" class="day-empty">
            暂无排课
          </div>
        </div>
      </div>
      <el-alert
        v-else
        :closable="false"
        type="info"
        :title="`共 ${schedules.length} 条上课安排，时间均为北京时间`"
      />
    </el-card>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>上课安排</h3>
        <el-tag type="info" effect="plain">{{ schedules.length }} 条排课</el-tag>
      </div>
      <el-table
        :data="schedules"
        v-loading="loading"
        :empty-text="onDate ? '当天没有排课' : '暂无课表，请联系管理员排课'"
      >
        <el-table-column prop="name" label="课程" min-width="150" /><el-table-column
          prop="teacher"
          label="教师"
          min-width="100"
        /><el-table-column prop="location" label="地点" min-width="120" />
        <el-table-column label="上课时间" min-width="180"
          ><template #default="{ row }"
            >{{ weekdays[row.weekday - 1] }} {{ row.start_time.slice(0, 5) }}–{{
              row.end_time.slice(0, 5)
            }}</template
          ></el-table-column
        >
        <el-table-column label="有效日期" min-width="200"
          ><template #default="{ row }"
            >{{ row.start_date }} 至 {{ row.end_date }}</template
          ></el-table-column
        >
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getMySchedules } from '@/api/schedule'
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const schedules = ref([]),
  onDate = ref(null),
  loading = ref(false)
let sequence = 0
async function load() {
  const request = ++sequence
  loading.value = true
  try {
    const result = await getMySchedules({ on_date: onDate.value || undefined })
    if (request === sequence) schedules.value = result.data || []
  } catch {
    if (request === sequence) schedules.value = []
  } finally {
    if (request === sequence) loading.value = false
  }
}
function reset() {
  onDate.value = null
  load()
}
onMounted(load)
</script>

<style scoped>
.date-filter {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.week-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(140px, 1fr));
  overflow-x: auto;
  gap: 10px;
}
.week-day {
  min-height: 160px;
  background: var(--campus-canvas);
  border-radius: 9px;
  padding: 10px;
}
.week-day h4 {
  text-align: center;
  color: var(--campus-muted);
  margin-bottom: 14px;
}
.schedule-block {
  display: flex;
  flex-direction: column;
  gap: 7px;
  background: var(--campus-accent-soft);
  border-left: 3px solid var(--campus-accent);
  border-radius: 6px;
  padding: 12px 9px;
  margin-bottom: 10px;
}
.schedule-block small,
.schedule-block span {
  color: var(--campus-muted);
  font-size: 11px;
}
.day-empty {
  color: var(--campus-muted);
  text-align: center;
  font-size: 12px;
  padding: 22px 0;
}
@media (max-width: 680px) {
  .week-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .week-day { min-height: 0; }
  .week-day h4 { text-align: start; margin-bottom: 8px; }
  .day-empty { text-align: start; padding: 6px 0; }
}
</style>
