<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>课表管理</h1>
        <p>为学生安排上课时间；同一课程可以分别安排给多个学生。</p>
      </div>
      <el-button type="primary" :icon="Plus" :disabled="fetching" @click="openCreate"
        >新增排课</el-button
      >
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <div class="filters">
          <el-select
            v-model="filters.student_id"
            filterable
            remote
            clearable
            :remote-method="searchStudents"
            :loading="studentsLoading"
            placeholder="按学生筛选"
            style="width: 230px"
            @change="search"
            ><el-option
              v-for="student in students"
              :key="student.id"
              :value="student.id"
              :label="`${student.name} (${student.username})`"
          /></el-select>
          <el-date-picker
            v-model="filters.on_date"
            value-format="YYYY-MM-DD"
            placeholder="按日期筛选"
            clearable
            @change="search"
          />
        </div>
        <div>
          <el-button @click="resetSearch">重置</el-button
          ><el-button type="primary" :icon="Search" @click="search">查询</el-button>
        </div>
      </div>
      <el-table :data="schedules" v-loading="loading" empty-text="暂无课表记录">
        <el-table-column label="学生" min-width="160"
          ><template #default="{ row }"
            >{{ row.student_name }} <span class="muted">({{ row.username }})</span></template
          ></el-table-column
        >
        <el-table-column
          prop="name"
          label="课程"
          min-width="150"
          show-overflow-tooltip
        /><el-table-column prop="teacher" label="教师" min-width="100" /><el-table-column
          prop="location"
          label="地点"
          min-width="120"
          show-overflow-tooltip
        />
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
        <el-table-column label="操作" width="135" fixed="right"
          ><template #default="{ row }"
            ><el-button type="primary" link :disabled="fetching" @click="openEdit(row.id)"
              >编辑</el-button
            ><el-popconfirm title="确认删除这条排课？" @confirm="remove(row.id)"
              ><template #reference
                ><el-button type="danger" link :disabled="!!removing">删除</el-button></template
              ></el-popconfirm
            ></template
          ></el-table-column
        >
      </el-table>
      <el-pagination
        class="pagination"
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="load"
        @size-change="changeSize"
      />
    </el-card>
    <el-dialog
      v-model="visible"
      :title="form.id ? '编辑排课' : '新增排课'"
      width="min(620px, 94vw)"
      :close-on-click-modal="!saving"
      :close-on-press-escape="!saving"
      :show-close="!saving"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving">
        <el-form-item label="学生" prop="student_id"
          ><el-select
            v-model="form.student_id"
            filterable
            remote
            :remote-method="searchStudents"
            :loading="studentsLoading"
            placeholder="搜索学生账号或姓名"
            style="width: 100%"
            ><el-option
              v-for="student in students"
              :key="student.id"
              :value="student.id"
              :label="`${student.name} (${student.username})${student.status === 0 ? ' · 已禁用' : ''}`" /></el-select
        ></el-form-item>
        <el-form-item label="课程" prop="course_id"
          ><el-select
            v-model="form.course_id"
            filterable
            remote
            :remote-method="searchCourses"
            :loading="coursesLoading"
            placeholder="搜索课程名称或教师"
            style="width: 100%"
            @change="courseChanged"
            ><el-option
              v-for="course in courses"
              :key="course.id"
              :value="course.id"
              :label="`${course.name} · ${course.teacher || '教师待定'} (#${course.id})`"
          /></el-select>
          <div class="muted">课程不存在时，请先到“课程管理”新增。</div></el-form-item
        >
        <el-form-item label="每周上课日" prop="weekday"
          ><el-select v-model="form.weekday"
            ><el-option
              v-for="(day, index) in weekdays"
              :key="day"
              :value="index + 1"
              :label="day" /></el-select
        ></el-form-item>
        <div class="form-grid">
          <el-form-item label="开始时间" prop="start_time"
            ><el-time-picker
              v-model="form.start_time"
              value-format="HH:mm:ss"
              format="HH:mm"
              style="width: 100%" /></el-form-item
          ><el-form-item label="结束时间" prop="end_time"
            ><el-time-picker
              v-model="form.end_time"
              value-format="HH:mm:ss"
              format="HH:mm"
              style="width: 100%"
          /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="有效开始日期" prop="start_date"
            ><el-date-picker
              v-model="form.start_date"
              value-format="YYYY-MM-DD"
              style="width: 100%" /></el-form-item
          ><el-form-item label="有效结束日期" prop="end_date"
            ><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" style="width: 100%"
          /></el-form-item>
        </div>
        <el-form-item label="上课地点"
          ><el-input v-model="form.location" maxlength="100" /></el-form-item
        ><el-form-item label="备注"
          ><el-input
            v-model="form.notes"
            type="textarea"
            :rows="3"
            maxlength="4000"
            show-word-limit
        /></el-form-item>
      </el-form>
      <template #footer
        ><el-button :disabled="saving" @click="visible = false">取消</el-button
        ><el-button type="primary" :loading="saving" @click="save">保存排课</el-button></template
      >
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getScheduleList,
  getScheduleDetail,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  getStudentOptions
} from '@/api/schedule'
import { getCourseList } from '@/api/course'
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const schedules = ref([]),
  total = ref(0),
  loading = ref(false),
  visible = ref(false),
  saving = ref(false),
  fetching = ref(false),
  removing = ref(null),
  formRef = ref()
const students = ref([]),
  courses = ref([]),
  studentsLoading = ref(false),
  coursesLoading = ref(false)
const filters = reactive({ student_id: null, on_date: null }),
  params = reactive({ page: 1, page_size: 10, student_id: undefined, on_date: undefined }),
  form = reactive({})
let loadSequence = 0,
  studentSequence = 0,
  courseSequence = 0
const fields = [
  'student_id',
  'course_id',
  'weekday',
  'start_time',
  'end_time',
  'start_date',
  'end_date',
  'location',
  'notes'
]
const rules = Object.fromEntries(
  fields
    .filter((key) => !['location', 'notes'].includes(key))
    .map((key) => [key, [{ required: true, message: '请填写此项', trigger: 'change' }]])
)
const dateString = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
async function searchStudents(query = '') {
  const sequence = ++studentSequence
  studentsLoading.value = true
  try {
    const options = (await getStudentOptions(query)).data || []
    if (sequence === studentSequence) {
      const selected = students.value.filter((row) =>
        [filters.student_id, form.student_id].includes(row.id)
      )
      students.value = [...new Map([...selected, ...options].map((row) => [row.id, row])).values()]
    }
  } catch {
    /* request interceptor displays errors */
  } finally {
    if (sequence === studentSequence) studentsLoading.value = false
  }
}
async function searchCourses(query = '') {
  const sequence = ++courseSequence
  coursesLoading.value = true
  try {
    const options =
      (await getCourseList({ page: 1, page_size: 30, keywords: query })).data?.list || []
    if (sequence === courseSequence) {
      const selected = courses.value.find((row) => row.id === form.course_id)
      courses.value =
        selected && !options.some((row) => row.id === selected.id)
          ? [selected, ...options]
          : options
    }
  } catch {
    /* request interceptor displays errors */
  } finally {
    if (sequence === courseSequence) coursesLoading.value = false
  }
}
async function load() {
  const sequence = ++loadSequence
  loading.value = true
  try {
    const result = (await getScheduleList({ ...params })).data
    if (sequence === loadSequence) {
      schedules.value = result?.list || []
      total.value = result?.total || 0
    }
  } catch {
    /* retain current table on failure */
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}
function search() {
  params.student_id = filters.student_id || undefined
  params.on_date = filters.on_date || undefined
  params.page = 1
  load()
}
function resetSearch() {
  filters.student_id = null
  filters.on_date = null
  search()
}
function changeSize() {
  params.page = 1
  load()
}
async function showForm(data) {
  Object.assign(form, data)
  visible.value = true
  await nextTick()
  formRef.value?.clearValidate()
  searchStudents()
  searchCourses()
}
function openCreate() {
  const end = new Date()
  end.setMonth(end.getMonth() + 5)
  showForm({
    id: null,
    student_id: filters.student_id,
    course_id: null,
    weekday: 1,
    start_time: '08:00:00',
    end_time: '09:40:00',
    start_date: dateString(new Date()),
    end_date: dateString(end),
    location: '',
    notes: ''
  })
}
async function openEdit(id) {
  if (fetching.value) return
  fetching.value = true
  try {
    const row = (await getScheduleDetail(id)).data
    students.value = [
      ...students.value.filter((student) => student.id !== row.student_id),
      { id: row.student_id, name: row.student_name, username: row.username }
    ]
    courses.value = [{ id: row.course_id, name: row.name, teacher: row.teacher }]
    await showForm(row)
  } catch {
    /* request interceptor displays errors */
  } finally {
    fetching.value = false
  }
}
function courseChanged(id) {
  const course = courses.value.find((row) => row.id === id)
  if (course && !form.location) form.location = course.location || ''
}
async function save() {
  if (saving.value || !(await formRef.value.validate().catch(() => false))) return
  if (form.end_time <= form.start_time || form.end_date < form.start_date)
    return ElMessage.warning('请检查起止时间和日期')
  const start = new Date(`${form.start_date}T00:00:00Z`),
    end = new Date(`${form.end_date}T00:00:00Z`)
  if ((end - start) / 86400000 < (form.weekday - (start.getUTCDay() || 7) + 7) % 7)
    return ElMessage.warning('有效日期范围内没有选定的上课日')
  saving.value = true
  try {
    const data = Object.fromEntries(fields.map((key) => [key, form[key]]))
    if (form.id) await updateSchedule(form.id, data)
    else await createSchedule(data)
    visible.value = false
    ElMessage.success('排课已保存')
    await load()
  } catch {
    /* request interceptor displays errors */
  } finally {
    saving.value = false
  }
}
async function remove(id) {
  if (removing.value) return
  removing.value = id
  try {
    await deleteSchedule(id)
    if (schedules.value.length === 1 && params.page > 1) params.page--
    ElMessage.success('排课已删除')
    await load()
  } catch {
    /* interceptor displays errors */
  } finally {
    removing.value = null
  }
}
onMounted(() => {
  load()
  searchStudents()
})
</script>

<style scoped>
.filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
  overflow-x: auto;
}
</style>
