<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>我的课程</h1>
        <p>查看自己的课程资料；上课日期与时间请以“我的课表”为准。</p>
      </div>
      <el-button @click="router.push('/manager/my-schedules')">查看我的课表</el-button>
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>课程列表</h3>
        <el-input
          v-model="keyword"
          placeholder="搜索课程或教师"
          clearable
          style="width: 240px"
          :prefix-icon="Search"
        />
      </div>
      <el-table :data="filtered" v-loading="loading" empty-text="暂无课程，请联系管理员排课">
        <el-table-column prop="name" label="课程" min-width="150" /><el-table-column
          prop="teacher"
          label="教师"
          min-width="100"
        /><el-table-column prop="notes" label="课程备注" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { getCourses } from '@/api/campus'
const router = useRouter(),
  courses = ref([]),
  keyword = ref(''),
  loading = ref(false)
const filtered = computed(() =>
  courses.value.filter((item) =>
    `${item.name} ${item.teacher}`.toLowerCase().includes(keyword.value.toLowerCase())
  )
)
onMounted(async () => {
  loading.value = true
  try {
    courses.value = (await getCourses()).data || []
  } finally {
    loading.value = false
  }
})
</script>
