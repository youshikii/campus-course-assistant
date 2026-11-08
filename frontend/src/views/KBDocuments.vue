<template>
  <div class="page-stack">
    <div class="page-heading">
      <div>
        <h1>课程资料管理</h1>
        <p>批量管理课程文件，查看提取的原文内容。</p>
      </div>
    </div>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>批量上传</h3>
        <el-tag effect="plain" type="info">PDF / DOCX / TXT / MD</el-tag>
      </div>
      <el-upload
        v-model:file-list="files"
        multiple
        :auto-upload="false"
        :limit="20"
        accept=".pdf,.docx,.txt,.md"
        :disabled="uploading"
        :on-exceed="onExceed"
      >
        <template #trigger><el-button :disabled="uploading">选择资料文件</el-button></template>
        <el-button
          class="submit-upload"
          type="primary"
          :loading="uploading"
          :disabled="!files.length"
          @click="upload"
          >整批上传（{{ files.length }} 个）</el-button
        >
        <template #tip
          ><p class="upload-tip">
            每批最多 20 个文件、合计 50MB，单个文件不超过 10MB。任一文件失败，本批全部不保存。
          </p></template
        >
      </el-upload>
      <el-alert v-if="batchError" :title="batchError" type="error" :closable="false" show-icon />
    </el-card>
    <el-card shadow="never">
      <div class="section-toolbar">
        <h3>资料列表 · {{ total }} 份</h3>
        <div class="search-box">
          <el-input
            v-model="keywords"
            clearable
            placeholder="搜索文件名"
            maxlength="100"
            @keyup.enter="search"
          />
          <el-button :disabled="uploading" @click="search">查询</el-button>
          <el-button :disabled="uploading" @click="load">刷新</el-button>
        </div>
      </div>
      <el-table :data="rows" v-loading="loading" empty-text="尚未上传课程资料">
        <el-table-column prop="file_name" label="文件名称" min-width="180" />
        <el-table-column prop="file_type" label="类型" width="90"
          ><template #default="{ row }">{{
            row.file_type.toUpperCase()
          }}</template></el-table-column
        >
        <el-table-column label="大小" width="110"
          ><template #default="{ row }">{{ fileSize(row.file_size) }}</template></el-table-column
        >
        <el-table-column prop="file_path" label="存储位置" min-width="180" show-overflow-tooltip />
        <el-table-column label="上传时间" min-width="170"
          ><template #default="{ row }">{{
            row.create_time.replace('T', ' ').slice(0, 19)
          }}</template></el-table-column
        >
        <el-table-column label="操作" width="170"
          ><template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="uploading || deleting === row.id"
              @click="preview(row)"
              >文本预览</el-button
            >
            <el-popconfirm title="确认删除此资料及文件？" @confirm="remove(row)"
              ><template #reference>
                <el-button link type="danger" :disabled="uploading || !!deleting">删除</el-button>
              </template></el-popconfirm
            >
          </template></el-table-column
        >
      </el-table>
      <el-pagination
        v-model:current-page="page"
        :page-size="10"
        :total="total"
        layout="prev, pager, next, total"
        :disabled="uploading"
        @current-change="load"
      />
    </el-card>
    <el-dialog v-model="previewVisible" :title="previewName" width="min(860px, 94vw)">
      <div v-loading="previewLoading">
        <pre class="plain-preview">{{ previewText }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getKBDocuments,
  uploadKBDocuments,
  previewKBDocument,
  deleteKBDocument
} from '@/api/kbDocuments'

const files = ref([]),
  rows = ref([]),
  total = ref(0),
  page = ref(1),
  keywords = ref('')
const uploading = ref(false),
  loading = ref(false),
  deleting = ref(null),
  batchError = ref('')
const previewVisible = ref(false),
  previewLoading = ref(false),
  previewName = ref(''),
  previewText = ref('')
let listRequest = 0,
  previewRequest = 0
function fileSize(size) {
  return size >= 1024 * 1024
    ? `${(size / 1024 / 1024).toFixed(2)} MB`
    : `${(size / 1024).toFixed(1)} KB`
}
function onExceed() {
  ElMessage.warning('每批最多选择 20 个文件')
}
async function load() {
  const requestId = ++listRequest
  loading.value = true
  try {
    const result = (
      await getKBDocuments({ page: page.value, page_size: 10, keywords: keywords.value })
    ).data
    if (requestId !== listRequest) return
    if (!result.list.length && page.value > 1) {
      page.value = Math.max(1, Math.ceil(result.total / 10))
      return load()
    }
    rows.value = result.list
    total.value = result.total
  } finally {
    if (requestId === listRequest) loading.value = false
  }
}
function search() {
  page.value = 1
  return load()
}
async function upload() {
  if (uploading.value || !files.value.length) return
  const batch = files.value.map((file) => file.raw)
  if (
    batch.some(
      (file) =>
        !file ||
        !/\.(pdf|docx|txt|md)$/i.test(file.name) ||
        !file.size ||
        file.size > 10 * 1024 * 1024
    ) ||
    batch.reduce((size, file) => size + file.size, 0) > 50 * 1024 * 1024
  ) {
    batchError.value = '请选择支持类型的非空文件，单个不超过 10MB，整批不超过 50MB。'
    return
  }
  uploading.value = true
  batchError.value = ''
  try {
    const result = (await uploadKBDocuments(batch)).data
    ElMessage.success(`已上传 ${result.length} 份资料`)
    files.value = []
    page.value = 1
  } catch (error) {
    batchError.value = error.response?.data?.message || error.message || '上传失败，请重试。'
  } finally {
    uploading.value = false
    await load()
  }
}
async function preview(row) {
  const requestId = ++previewRequest
  previewName.value = row.file_name
  previewText.value = ''
  previewVisible.value = true
  previewLoading.value = true
  try {
    const data = (await previewKBDocument(row.id)).data
    if (requestId === previewRequest) previewText.value = data.content
  } finally {
    if (requestId === previewRequest) previewLoading.value = false
  }
}
async function remove(row) {
  deleting.value = row.id
  try {
    const data = (await deleteKBDocument(row.id)).data
    if (data.cleanup_pending) ElMessage.warning('资料已移除，隔离文件待管理员清理。')
    else ElMessage.success('资料已删除')
    await load()
  } finally {
    deleting.value = null
  }
}
onMounted(load)
</script>

<style scoped>
.submit-upload {
  margin-left: 12px;
}
.upload-tip {
  color: var(--campus-muted);
  font-size: 12px;
  line-height: 1.8;
  margin: 10px 0;
}
.search-box {
  display: flex;
  gap: 10px;
  max-width: 470px;
}
.el-pagination {
  justify-content: flex-end;
  margin-top: 18px;
}
.plain-preview {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 65vh;
  overflow: auto;
  line-height: 1.8;
  color: var(--campus-text);
}
@media (max-width: 640px) {
  .section-toolbar {
    align-items: flex-start;
    gap: 12px;
    flex-direction: column;
  }
  .search-box {
    max-width: 100%;
  }
}
</style>
