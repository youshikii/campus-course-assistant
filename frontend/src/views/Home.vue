<template>
  <div class="page-stack overview" v-loading="loading">
    <header class="page-heading">
      <div>
        <div class="muted">{{ dateLabel }}</div>
        <h1>你好，{{ userInfo?.name || '同学' }}</h1>
        <p>查看今日课程，安排接下来的学习。</p>
      </div>
      <router-link to="/manager/assistant" class="overview-primary">
        <el-icon><ChatDotRound /></el-icon> 问智能助手
      </router-link>
    </header>

    <nav v-if="userInfo?.role === 'admin'" class="teacher-links" aria-label="教学管理快捷入口">
      <strong>教学管理</strong>
      <router-link to="/manager/schedule-management">安排课表 <el-icon><Right /></el-icon></router-link>
      <router-link to="/manager/course-management">维护课程 <el-icon><Right /></el-icon></router-link>
    </nav>

    <div class="home-grid">
      <section class="home-panel" aria-labelledby="today-title">
        <div class="home-panel-header">
          <div><h2 id="today-title">今日课表</h2><p class="muted">{{ todayCourses.length }} 节课</p></div>
          <router-link to="/manager/my-schedules" class="panel-link">查看全部 <el-icon><Right /></el-icon></router-link>
        </div>
        <p v-if="!todayCourses.length" class="empty-row">今天没有排课</p>
        <div v-for="course in todayCourses" :key="course.id" class="today-course">
          <div class="course-time">
            <strong>{{ course.start_time.slice(0, 5) }}</strong>
            <span>{{ course.end_time.slice(0, 5) }}</span>
          </div>
          <div class="row-copy">
            <strong>{{ course.name }}</strong>
            <p>{{ course.location || '地点待定' }} · {{ course.teacher || '教师待定' }}</p>
          </div>
        </div>
      </section>
      <section class="home-panel" aria-labelledby="plans-title">
        <div class="home-panel-header">
          <div><h2 id="plans-title">待完成计划</h2><p class="muted">{{ pendingPlanTotal }} 项待办</p></div>
          <router-link to="/manager/plans" class="panel-link">查看全部 <el-icon><Right /></el-icon></router-link>
        </div>
        <p v-if="!pendingPlans.length" class="empty-row">暂无待完成的学习计划</p>
        <router-link v-for="plan in pendingPlans" :key="plan.id" to="/manager/plans" class="home-plan">
          <el-icon><CircleCheck /></el-icon>
          <div class="row-copy">
            <strong>{{ plan.title }}</strong>
            <p>{{ plan.target_date ? `目标日期 ${plan.target_date}` : '未设置目标日期' }}</p>
          </div>
        </router-link>
      </section>
    </div>

    <nav class="stat-grid" aria-label="学习数据">
      <router-link v-for="stat in stats" :key="stat.label" :to="stat.path" class="stat-card">
        <div class="stat-label"><el-icon><component :is="stat.icon" /></el-icon>{{ stat.label }}</div>
        <strong>{{ stat.value }} <small>{{ stat.unit }}</small></strong>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Calendar, Reading, FolderOpened, List, Right, CircleCheck, ChatDotRound } from '@element-plus/icons-vue'
import { useUser } from '@/utils/user'
import { getCourses, getDocuments } from '@/api/campus'
import { getStudyPlans } from '@/api/studyPlan'
import { getMySchedules } from '@/api/schedule'
const { userInfo } = useUser()
const courses = ref([]),
  todayCourses = ref([]),
  documents = ref([]),
  plans = ref([]),
  pendingPlanTotal = ref(0),
  loading = ref(false)
const dateLabel = new Intl.DateTimeFormat('zh-CN', {
  dateStyle: 'full',
  timeZone: 'Asia/Shanghai'
}).format(new Date())
const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date())
const pendingPlans = computed(() => plans.value.filter((plan) => plan.status === 'pending'))
const stats = computed(() => [
  {
    label: '我的课程',
    value: courses.value.length,
    unit: '门',
    icon: Calendar,
    path: '/manager/courses'
  },
  {
    label: '今日课程',
    value: todayCourses.value.length,
    unit: '节',
    icon: Reading,
    path: '/manager/my-schedules'
  },
  {
    label: '已索引资料',
    value: documents.value.filter((doc) => doc.status === 'ready').length,
    unit: '份',
    icon: FolderOpened,
    path: '/manager/documents'
  },
  {
    label: '待完成计划',
    value: pendingPlanTotal.value,
    unit: '项',
    icon: List,
    path: '/manager/plans'
  }
])
onMounted(async () => {
  loading.value = true
  try {
    const results = await Promise.all([
      getCourses(),
      getMySchedules({ on_date: today }),
      getDocuments(),
      getStudyPlans({ page: 1, page_size: 4, status: 'pending' })
    ])
    courses.value = results[0].data || []
    todayCourses.value = results[1].data || []
    documents.value = results[2].data || []
    plans.value = results[3].data?.list || []
    pendingPlanTotal.value = results[3].data?.total || 0
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.overview { gap: 22px; }
.overview-primary {
  display: inline-flex; align-items: center; gap: 7px; padding: 9px 14px;
  border-radius: 8px; background: var(--campus-accent); color: white; font-weight: 600;
}
.overview-primary:hover { background: var(--el-color-primary-dark-2); }
.teacher-links {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; padding: 11px 15px;
  border: 1px solid var(--campus-line); border-radius: var(--campus-radius);
  background: var(--campus-surface);
}
.teacher-links a, .panel-link { display: inline-flex; align-items: center; gap: 5px; color: var(--campus-accent); }
.teacher-links a:hover, .panel-link:hover { text-decoration: underline; }
.home-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.home-panel, .stat-card {
  background: var(--campus-surface); border: 1px solid var(--campus-line); border-radius: var(--campus-radius);
}
.home-panel { padding: 18px; }
.home-panel-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding-bottom: 12px; }
.home-panel-header h2 { font-size: 18px; font-weight: 670; color: var(--campus-ink); }
.panel-link { font-size: 13px; white-space: nowrap; }
.empty-row { border-top: 1px solid var(--campus-line); padding: 14px 0 4px; color: var(--campus-muted); }
.today-course, .home-plan { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-top: 1px solid var(--campus-line); }
.course-time { min-width: 59px; font-variant-numeric: tabular-nums; }
.course-time strong { display: block; color: var(--campus-ink); }
.course-time span, .row-copy p { color: var(--campus-muted); font-size: 12px; }
.row-copy { min-width: 0; overflow-wrap: anywhere; }
.row-copy strong { color: var(--campus-ink); font-weight: 650; }
.home-plan .el-icon { color: var(--campus-accent); flex: none; }
.home-plan:hover .row-copy strong { color: var(--campus-accent); }
.stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.stat-card { padding: 12px 14px; }
.stat-card:hover { border-color: var(--campus-accent); }
.stat-label { display: flex; align-items: center; gap: 6px; color: var(--campus-muted); }
.stat-card strong { display: block; color: var(--campus-ink); font-size: 23px; font-variant-numeric: tabular-nums; }
.stat-card small { color: var(--campus-muted); font-size: 12px; font-weight: 400; }
@media (max-width: 960px) { .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .home-grid { grid-template-columns: 1fr; } }
</style>
