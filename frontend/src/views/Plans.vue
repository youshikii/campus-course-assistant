<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>学习计划</h1>
        <p>写下学习目标与行动安排，计划仅自己可见。</p>
      </div>
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>保存新计划</h3>
        <span class="muted">支持 Markdown 格式</span>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving">
        <div class="plan-form-row">
          <el-form-item label="计划标题" prop="title"
            ><el-input
              v-model="form.title"
              maxlength="120"
              placeholder="例如：本周高等数学复习计划"
              show-word-limit /></el-form-item
          ><el-form-item label="目标日期（可选）"
            ><el-date-picker
              v-model="form.target_date"
              value-format="YYYY-MM-DD"
              clearable
              placeholder="选择目标日期"
              style="width: 100%"
          /></el-form-item>
        </div>
        <el-form-item label="计划内容" prop="content"
          ><el-input
            v-model="form.content"
            type="textarea"
            :rows="6"
            maxlength="10000"
            show-word-limit
            placeholder="写下学习目标、具体步骤和时间安排…"
        /></el-form-item>
        <div class="save-actions">
          <el-button :disabled="saving" @click="resetForm">清空</el-button
          ><el-button type="primary" :loading="saving" @click="save">保存计划</el-button>
        </div>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <div class="section-toolbar">
        <div class="list-heading">
          <h3>我的计划</h3>
          <el-tag type="info" effect="plain">共 {{ total }} 份</el-tag>
        </div>
        <div class="list-heading">
          <span class="muted">按创建时间倒序</span
          ><el-button text :disabled="loading" @click="load">刷新</el-button>
        </div>
      </div>
      <div v-loading="loading" class="plan-list">
        <el-empty
          v-if="!loading && !plans.length"
          description="还没有学习计划，在上方填写并保存，或让助手帮你制定并保存"
          :image-size="80"
        />
        <article v-for="plan in plans" :key="plan.id" class="plan-item">
          <header class="plan-heading">
            <div>
              <h3>{{ plan.title }}</h3>
              <div class="muted">
                创建于 {{ displayTime(plan.create_time)
                }}<span v-if="plan.target_date"> · 目标日期 {{ plan.target_date }}</span>
              </div>
            </div>
            <el-tag :type="plan.status === 'completed' ? 'success' : 'warning'">{{
              plan.status === 'completed' ? '已完成' : '待完成'
            }}</el-tag>
          </header>
          <MarkdownContent :content="plan.content" />
          <div class="plan-actions">
            <el-button
              :type="plan.status === 'completed' ? 'default' : 'primary'"
              plain
              :loading="changing === plan.id"
              :disabled="!!changing || !!removing"
              @click="toggle(plan)"
              >{{ plan.status === 'completed' ? '重新开始' : '标记完成' }}</el-button
            ><el-popconfirm title="确认删除这份计划？" @confirm="remove(plan.id)"
              ><template #reference
                ><el-button
                  text
                  type="danger"
                  :loading="removing === plan.id"
                  :disabled="!!removing || !!changing"
                  >删除</el-button
                ></template
              ></el-popconfirm
            >
          </div>
        </article>
      </div>
      <el-pagination
        class="pagination"
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
        :total="total"
        :page-sizes="[5, 10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="load"
        @size-change="changeSize"
      />
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownContent from '@/components/MarkdownContent.vue'
import {
  getStudyPlans,
  saveStudyPlan,
  deleteStudyPlan,
  updateStudyPlanStatus
} from '@/api/studyPlan'
const plans = ref([]),
  total = ref(0),
  loading = ref(false),
  saving = ref(false),
  removing = ref(null),
  changing = ref(null),
  formRef = ref()
const form = reactive({ title: '', content: '', target_date: null })
const params = reactive({ page: 1, page_size: 10 })
let loadSequence = 0
const rules = {
  title: [{ required: true, whitespace: true, message: '请填写计划标题', trigger: 'blur' }],
  content: [{ required: true, whitespace: true, message: '请填写计划内容', trigger: 'blur' }]
}
const displayTime = (value) => (value ? value.replace('T', ' ').slice(0, 19) : '')
async function load() {
  const sequence = ++loadSequence
  loading.value = true
  try {
    const data = (await getStudyPlans({ ...params })).data
    if (sequence === loadSequence) {
      plans.value = data?.list || []
      total.value = data?.total || 0
    }
  } catch {
    /* request interceptor displays errors; retain existing list */
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}
async function resetForm() {
  Object.assign(form, { title: '', content: '', target_date: null })
  await nextTick()
  formRef.value?.clearValidate()
}
function changeSize() {
  params.page = 1
  load()
}
async function save() {
  if (saving.value || !(await formRef.value.validate().catch(() => false))) return
  saving.value = true
  try {
    await saveStudyPlan({ ...form })
    await resetForm()
    params.page = 1
    ElMessage.success('计划已保存')
    await load()
  } catch {
    /* keep input on failure */
  } finally {
    saving.value = false
  }
}
async function toggle(plan) {
  if (changing.value || removing.value) return
  changing.value = plan.id
  try {
    await updateStudyPlanStatus(plan.id, plan.status === 'completed' ? 'pending' : 'completed')
    await load()
  } catch {
    /* request interceptor displays errors */
  } finally {
    changing.value = null
  }
}
async function remove(id) {
  if (removing.value || changing.value) return
  removing.value = id
  try {
    await deleteStudyPlan(id)
    if (plans.value.length === 1 && params.page > 1) params.page--
    ElMessage.success('计划已删除')
    await load()
  } catch {
    /* request interceptor displays errors */
  } finally {
    removing.value = null
  }
}
onMounted(load)
</script>

<style scoped>
.plan-form-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 20px;
}
.save-actions,
.list-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.save-actions {
  justify-content: flex-end;
}
.plan-list {
  min-height: 80px;
}
.plan-item {
  border: 1px solid var(--campus-line);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 16px;
}
.plan-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.plan-heading h3 {
  font-size: 16px;
  margin-bottom: 8px;
  overflow-wrap: anywhere;
}
.plan-actions {
  display: flex;
  gap: 12px;
  border-top: 1px solid var(--campus-line);
  padding-top: 16px;
  margin-top: 20px;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
  overflow-x: auto;
}
@media (max-width: 700px) {
  .plan-form-row {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .plan-item {
    padding: 14px;
  }
}
</style>
