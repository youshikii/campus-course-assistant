<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>课程资料库</h1>
        <p>上传课程大纲与笔记，让回答有据可查。资料仅自己可见。</p>
      </div>
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>添加资料</h3>
        <el-tag type="info" effect="plain">PDF / DOCX / TXT / MD · 最大 10MB</el-tag>
      </div>
      <el-select
        v-model="courseId"
        clearable
        placeholder="关联课程（可选）"
        style="width: 260px; margin-bottom: 16px"
        ><el-option
          v-for="course in courses"
          :key="course.id"
          :label="course.name"
          :value="course.id"
      /></el-select>
      <el-upload
        drag
        :show-file-list="false"
        :http-request="upload"
        accept=".pdf,.docx,.txt,.md"
        :disabled="uploading"
        :before-upload="validateFile"
      >
        <el-icon size="32" color="var(--campus-accent)"><UploadFilled /></el-icon>
        <div style="margin-top: 12px">
          {{ uploading ? '正在解析并建立向量索引，请稍候…' : '拖入课程资料，或点击选择文件' }}
        </div>
        <template #tip
          ><div class="muted" style="margin-top: 10px">
            支持含文本的 PDF（最多 100 页）；纯文本请使用 UTF-8。提取文本上限 60KB，较大文档请拆分。
          </div></template
        >
      </el-upload>
    </el-card>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>我的资料</h3>
        <el-button text @click="load">刷新</el-button>
      </div>
      <el-table
        :data="documents"
        v-loading="loading"
        empty-text="上传第一份课程资料，开始建立你的知识库"
      >
        <el-table-column prop="name" label="文档" min-width="180" /><el-table-column
          label="关联课程"
          min-width="120"
          ><template #default="{ row }">{{
            courses.find((item) => item.id === row.course_id)?.name || '通用资料'
          }}</template></el-table-column
        >
        <el-table-column label="索引状态" width="120"
          ><template #default="{ row }"
            ><el-tooltip :content="row.error || '文档索引状态'"
              ><el-tag
                :type="
                  row.status === 'ready'
                    ? 'success'
                    : row.status === 'failed'
                      ? 'danger'
                      : 'warning'
                "
                >{{ statusNames[row.status] || row.status }}</el-tag
              ></el-tooltip
            ></template
          ></el-table-column
        >
        <el-table-column prop="chunk_count" label="片段数" width="90" />
        <el-table-column label="操作" width="230"
          ><template #default="{ row }"
            ><el-button link type="primary" @click="preview(row.id)">查看</el-button
            ><el-button
              link
              type="primary"
              :loading="indexing === row.id"
              :disabled="!!indexing"
              @click="reindex(row.id)"
              >重建索引</el-button
            ><el-popconfirm title="删除资料及其索引？" @confirm="remove(row.id)"
              ><template #reference
                ><el-button link type="danger" :disabled="indexing === row.id"
                  >删除</el-button
                ></template
              ></el-popconfirm
            ></template
          ></el-table-column
        >
      </el-table>
    </el-card>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>检索试验台</h3>
        <span class="muted">查看助手将使用的原文片段</span>
      </div>
      <div style="display: flex; gap: 10px">
        <el-input
          v-model="query"
          placeholder="例如：高等数学的考核方式是什么？"
          maxlength="2000"
          @keyup.enter="search"
        /><el-button type="primary" :loading="searching" @click="search">检索</el-button>
      </div>
      <el-empty
        v-if="searched && !results.length"
        description="未检索到资料，请先上传并成功建立索引"
        :image-size="70"
      />
      <div v-for="source in results" :key="source.citation" class="source-preview">
        <strong>{{ source.name }} · {{ source.citation }}</strong>
        <p>{{ source.text }}</p>
      </div>
    </el-card>
    <el-dialog v-model="previewVisible" :title="currentDocument?.name" width="min(780px, 94vw)">
      <pre class="document-text">{{ currentDocument?.content }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import {
  getCourses,
  getDocuments,
  uploadDocument,
  indexDocument,
  deleteDocument,
  searchDocuments,
  getDocument
} from '@/api/campus'
const documents = ref([]),
  courses = ref([]),
  courseId = ref(),
  loading = ref(false),
  uploading = ref(false),
  indexing = ref(null)
const query = ref(''),
  results = ref([]),
  searching = ref(false),
  searched = ref(false),
  previewVisible = ref(false),
  currentDocument = ref(null)
const statusNames = { ready: '可检索', failed: '索引失败', pending: '待索引' }
async function load() {
  loading.value = true
  try {
    documents.value = (await getDocuments()).data || []
  } finally {
    loading.value = false
  }
}
function validateFile(file) {
  if (file.size > 10 * 1024 * 1024 || !/\.(pdf|docx|txt|md)$/i.test(file.name)) {
    ElMessage.warning('请选择 10MB 以内的 PDF、DOCX、TXT 或 MD 文档')
    return false
  }
  return true
}
async function upload({ file, onSuccess, onError }) {
  uploading.value = true
  try {
    const res = await uploadDocument(file, courseId.value)
    onSuccess(res)
    ElMessage[res.data.status === 'ready' ? 'success' : 'warning'](
      res.data.status === 'ready' ? '资料已入库，可以向助手提问了' : res.data.error
    )
    await load()
  } catch (error) {
    onError(error)
  } finally {
    uploading.value = false
  }
}
async function reindex(id) {
  indexing.value = id
  try {
    const res = await indexDocument(id)
    ElMessage[res.data.status === 'ready' ? 'success' : 'warning'](
      res.data.status === 'ready' ? '索引已更新' : res.data.error
    )
    await load()
  } finally {
    indexing.value = null
  }
}
async function remove(id) {
  await deleteDocument(id)
  ElMessage.success('资料已删除')
  await load()
}
async function preview(id) {
  currentDocument.value = (await getDocument(id)).data
  previewVisible.value = true
}
async function search() {
  if (!query.value.trim() || searching.value) return
  searching.value = true
  try {
    results.value =
      (await searchDocuments({ query: query.value, course_id: courseId.value || null })).data || []
    searched.value = true
  } finally {
    searching.value = false
  }
}
onMounted(async () => {
  await load()
  courses.value = (await getCourses()).data || []
})
</script>

<style scoped>
.source-preview {
  padding: 16px;
  background: var(--campus-canvas);
  border-radius: 8px;
  margin-top: 14px;
}
.source-preview p {
  margin-top: 8px;
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--campus-muted);
}
.document-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 65vh;
  overflow: auto;
  font-family: inherit;
  line-height: 1.9;
}
</style>
