<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>课程管理</h1>
        <p>维护课程基础信息，学生上课安排请到“课表管理”单独设置。</p>
      </div>
      <el-button type="primary" :icon="Plus" :disabled="fetching" @click="openCreate"
        >新增课程</el-button
      >
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <el-input
          v-model="keywords"
          placeholder="搜索课程名称或教师"
          clearable
          :prefix-icon="Search"
          style="width: 280px"
          maxlength="100"
          @keyup.enter="search"
          @clear="search"
        />
        <div>
          <el-button @click="resetSearch">重置</el-button
          ><el-button type="primary" :icon="Search" @click="search">查询</el-button>
        </div>
      </div>
      <el-table :data="courses" v-loading="loading" empty-text="暂无课程，点击右上角新增">
        <el-table-column prop="name" label="课程名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="所属用户" min-width="150"
          ><template #default="{ row }"
            >{{ row.user_name }} <span class="muted">({{ row.username }})</span></template
          ></el-table-column
        >
        <el-table-column prop="teacher" label="教师" min-width="100" show-overflow-tooltip />
        <el-table-column prop="location" label="地点" min-width="110" show-overflow-tooltip />
        <el-table-column label="上课时间" min-width="175"
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
        <el-table-column label="操作" width="175" fixed="right"
          ><template #default="{ row }">
            <el-button type="primary" link :disabled="fetching" @click="openDetail(row.id)"
              >详情</el-button
            >
            <el-button type="primary" link :disabled="fetching" @click="openEdit(row.id)"
              >编辑</el-button
            >
            <el-popconfirm
              title="确认删除此课程？关联课表和资料需先清理。"
              width="260"
              @confirm="remove(row.id)"
              ><template #reference
                ><el-button type="danger" link :disabled="removing === row.id"
                  >删除</el-button
                ></template
              ></el-popconfirm
            >
          </template></el-table-column
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
      :title="form.id ? '编辑课程' : '新增课程'"
      width="min(600px, 94vw)"
      :close-on-click-modal="!saving"
      :close-on-press-escape="!saving"
      :show-close="!saving"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving">
        <el-form-item label="课程名称" prop="name"
          ><el-input v-model="form.name" maxlength="100" placeholder="例如：高等数学"
        /></el-form-item>
        <el-form-item label="所属用户" prop="user_id">
          <el-select
            v-model="form.user_id"
            filterable
            remote
            :remote-method="searchUsers"
            :loading="usersLoading"
            placeholder="输入账号或姓名搜索用户"
            style="width: 100%"
          >
            <el-option
              v-for="user in users"
              :key="user.id"
              :value="user.id"
              :label="`${user.name} (${user.username})${user.status === 0 ? ' · 已禁用' : ''}`"
            />
          </el-select>
          <div class="muted">课程归属用于课程与资料权限；学生上课安排请到“课表管理”设置。</div>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="任课教师"
            ><el-input v-model="form.teacher" maxlength="100" /></el-form-item
          ><el-form-item label="上课地点"
            ><el-input v-model="form.location" maxlength="100"
          /></el-form-item>
        </div>
        <el-form-item label="每周上课日" prop="weekday"
          ><el-select v-model="form.weekday"
            ><el-option
              v-for="(day, index) in weekdays"
              :key="day"
              :label="day"
              :value="index + 1" /></el-select
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
          <el-form-item label="学期开始" prop="start_date"
            ><el-date-picker
              v-model="form.start_date"
              value-format="YYYY-MM-DD"
              style="width: 100%" /></el-form-item
          ><el-form-item label="学期结束" prop="end_date"
            ><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" style="width: 100%"
          /></el-form-item>
        </div>
        <el-form-item label="备注"
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
        ><el-button type="primary" :loading="saving" @click="save">保存课程</el-button></template
      >
    </el-dialog>
    <el-dialog v-model="detailVisible" title="课程详情" width="min(700px, 94vw)">
      <el-descriptions v-if="detail" :column="2" border>
        <el-descriptions-item label="课程名称" :span="2">{{ detail.name }}</el-descriptions-item>
        <el-descriptions-item label="所属用户" :span="2"
          >{{ detail.user_name }} ({{ detail.username }})</el-descriptions-item
        >
        <el-descriptions-item label="任课教师">{{
          detail.teacher || '未填写'
        }}</el-descriptions-item>
        <el-descriptions-item label="上课地点">{{
          detail.location || '未填写'
        }}</el-descriptions-item>
        <el-descriptions-item label="上课时间" :span="2"
          >{{ weekdays[detail.weekday - 1] }} {{ detail.start_time.slice(0, 5) }}–{{
            detail.end_time.slice(0, 5)
          }}</el-descriptions-item
        >
        <el-descriptions-item label="学期开始">{{ detail.start_date }}</el-descriptions-item
        ><el-descriptions-item label="学期结束">{{ detail.end_date }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2"
          ><div class="notes-text">{{ detail.notes || '无' }}</div></el-descriptions-item
        >
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getCourseList,
  getCourseDetail,
  createCourse,
  updateCourse,
  deleteCourse
} from '@/api/course'
import { getUserPageList } from '@/api/user'
import { getUserInfo } from '@/utils/auth'

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const courses = ref([]),
  total = ref(0),
  keywords = ref(''),
  loading = ref(false)
const visible = ref(false),
  detailVisible = ref(false),
  detail = ref(null),
  fetching = ref(false)
const saving = ref(false),
  removing = ref(null),
  formRef = ref(),
  users = ref([]),
  usersLoading = ref(false)
const params = reactive({ page: 1, page_size: 10, keywords: '' })
const form = reactive({})
let loadSequence = 0,
  userSequence = 0
const rules = Object.fromEntries(
  ['name', 'user_id', 'weekday', 'start_time', 'end_time', 'start_date', 'end_date'].map((key) => [
    key,
    [{ required: true, message: '请填写此项', trigger: 'change' }]
  ])
)
const dateString = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
function keepSelectedUser(options) {
  const selected = users.value.find((user) => user.id === form.user_id)
  users.value =
    selected && !options.some((user) => user.id === selected.id) ? [selected, ...options] : options
}
async function searchUsers(query = '') {
  const sequence = ++userSequence
  usersLoading.value = true
  try {
    const result = await getUserPageList({ page: 1, page_size: 30, keywords: query })
    if (sequence === userSequence) keepSelectedUser(result.data?.list || [])
  } catch {
    /* request interceptor displays the error */
  } finally {
    if (sequence === userSequence) usersLoading.value = false
  }
}
async function load() {
  const sequence = ++loadSequence
  loading.value = true
  try {
    const result = await getCourseList({ ...params })
    if (sequence === loadSequence) {
      courses.value = result.data?.list || []
      total.value = result.data?.total || 0
    }
  } catch {
    /* keep the current table on failure */
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}
function search() {
  params.keywords = keywords.value.trim()
  params.page = 1
  load()
}
function resetSearch() {
  keywords.value = ''
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
  searchUsers()
}
function openCreate() {
  const current = getUserInfo(),
    end = new Date()
  end.setMonth(end.getMonth() + 5)
  users.value = current ? [current] : []
  showForm({
    id: null,
    user_id: current?.id,
    name: '',
    teacher: '',
    location: '',
    weekday: 1,
    start_time: '08:00:00',
    end_time: '09:40:00',
    start_date: dateString(new Date()),
    end_date: dateString(end),
    notes: ''
  })
}
async function openEdit(id) {
  if (fetching.value) return
  fetching.value = true
  try {
    const data = (await getCourseDetail(id)).data
    users.value = [{ id: data.user_id, name: data.user_name, username: data.username }]
    await showForm(data)
  } catch {
    /* request interceptor displays the error */
  } finally {
    fetching.value = false
  }
}
async function openDetail(id) {
  if (fetching.value) return
  fetching.value = true
  try {
    detail.value = (await getCourseDetail(id)).data
    detailVisible.value = true
  } catch {
    /* request interceptor displays the error */
  } finally {
    fetching.value = false
  }
}
async function save() {
  if (saving.value || !(await formRef.value.validate().catch(() => false))) return
  if (!form.name.trim() || form.end_time <= form.start_time || form.end_date < form.start_date)
    return ElMessage.warning('请检查课程名称及起止时间、日期')
  saving.value = true
  const data = Object.fromEntries(
    [
      'user_id',
      'name',
      'teacher',
      'location',
      'weekday',
      'start_time',
      'end_time',
      'start_date',
      'end_date',
      'notes'
    ].map((key) => [key, form[key]])
  )
  try {
    if (form.id) await updateCourse(form.id, data)
    else await createCourse(data)
    visible.value = false
    ElMessage.success('课程已保存')
    await load()
  } catch {
    /* request interceptor displays the error */
  } finally {
    saving.value = false
  }
}
async function remove(id) {
  if (removing.value) return
  removing.value = id
  try {
    await deleteCourse(id)
    if (courses.value.length === 1 && params.page > 1) params.page--
    ElMessage.success('课程已删除')
    await load()
  } catch {
    /* request interceptor displays the error */
  } finally {
    removing.value = null
  }
}
onMounted(load)
</script>

<style scoped>
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
  overflow-x: auto;
}
.notes-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
