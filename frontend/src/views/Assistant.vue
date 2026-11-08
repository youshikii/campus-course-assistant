<template>
  <div class="assistant-shell">
    <aside class="session-sidebar">
      <el-button
        type="primary"
        plain
        :icon="Plus"
        :disabled="busy || sessionLoading"
        @click="newSession"
        >开启新对话</el-button
      >
      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentId, disabled: busy || sessionLoading }"
          @click="selectSession(session.id)"
        >
          <el-icon><ChatDotRound /></el-icon><span>{{ session.title }}</span
          ><el-button
            text
            size="small"
            :icon="Delete"
            :disabled="busy || sessionLoading"
            aria-label="删除会话"
            @click.stop="removeSession(session.id)"
          />
        </div>
      </div>
      <div class="sidebar-tip">
        <el-icon><Lock /></el-icon> 课表与资料仅限当前账号
      </div>
    </aside>
    <section class="chat-main">
      <header class="chat-header">
        <div>
          <h2>课程智能助手</h2>
          <span class="muted">查课表 · 读资料 · 制定学习计划</span>
        </div>
        <el-tag effect="plain">{{ config.model || 'DeepSeek' }}</el-tag>
      </header>
      <el-alert
        v-if="!config.llm_configured"
        type="warning"
        :closable="false"
        title="尚未配置模型密钥，请在后端 .env 中填写 LLM_API_KEY。"
      />
      <div ref="scrollArea" class="chat-scroll" v-loading="sessionLoading">
        <div v-if="!messages.length" class="chat-welcome">
          <div class="welcome-mark">
            <el-icon size="32"><Reading /></el-icon>
          </div>
          <h1>让每一门课，学得更明白。</h1>
          <p>我可以结合你的课表与课程资料，帮你整理学习安排。</p>
          <div class="suggestions">
            <button
              v-for="prompt in prompts"
              :key="prompt"
              :disabled="busy || sessionLoading || !config.llm_configured"
              @click="send(prompt)"
            >
              {{ prompt }} <span>↗</span>
            </button>
          </div>
        </div>
        <article
          v-for="(message, index) in messages"
          :key="message.id || index"
          class="chat-message"
          :class="message.role"
        >
          <div class="message-avatar">
            <el-icon><User v-if="message.role === 'user'" /><Reading v-else /></el-icon>
          </div>
          <div class="message-body">
            <div class="message-label">{{ message.role === 'user' ? '你' : '课程助手' }}</div>
            <div v-if="message.role === 'user'" class="user-text">{{ message.content }}</div>
            <template v-else>
              <div v-if="message.events?.length" class="tool-events">
                <div v-for="event in message.events" :key="event.id">
                  <el-icon :class="{ 'is-loading': event.status === 'running' }"
                    ><Loading v-if="event.status === 'running'" /><CircleClose
                      v-else-if="event.status === 'error'" /><CircleCheck v-else /></el-icon
                  ><span>{{ toolNames[event.name] || event.name }}</span
                  ><small>{{
                    event.status === 'running'
                      ? '进行中'
                      : event.status === 'error'
                        ? '失败'
                        : '完成'
                  }}</small>
                </div>
              </div>
              <MarkdownContent :content="message.content" />
              <div v-if="busy && index === messages.length - 1" class="generation-status">
                <span class="status-dot" />{{ status }}
              </div>
              <el-collapse v-if="message.sources?.length" class="citation-list"
                ><el-collapse-item
                  :title="`参考来源 · ${message.sources.length} 个原文片段`"
                  name="sources"
                  ><div v-for="source in message.sources" :key="source.citation" class="citation">
                    <strong>[{{ source.citation }}] {{ source.name }}</strong>
                    <p>{{ source.text }}</p>
                  </div></el-collapse-item
                ></el-collapse
              >
            </template>
          </div>
        </article>
      </div>
      <footer class="chat-composer">
        <div class="composer-box">
          <el-input
            v-model="input"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            resize="none"
            maxlength="6000"
            placeholder="问问课程内容，或让我帮你安排学习…"
            :disabled="busy || sessionLoading || !config.llm_configured"
            @keydown="handleKey"
          />
          <div class="composer-bottom">
            <span>Enter 发送 · Shift + Enter 换行</span
            ><el-button v-if="busy" type="danger" plain @click="stop">停止生成</el-button
            ><el-button
              v-else
              type="primary"
              :icon="Promotion"
              :disabled="!input.trim() || sessionLoading || !config.llm_configured"
              @click="send()"
              >发送</el-button
            >
          </div>
        </div>
        <p class="composer-note">
          回答可能存在误差，请结合课程原文核对。工具执行状态不代表模型内部推理。
        </p>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Delete,
  ChatDotRound,
  Lock,
  Reading,
  User,
  Loading,
  CircleCheck,
  CircleClose,
  Promotion
} from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'
import { getChatConfig, getSessions, createSession, getMessages, deleteSession } from '@/api/campus'
import { streamChat } from '@/api/chat'
const sessions = ref([]),
  currentId = ref(null),
  messages = ref([]),
  input = ref(''),
  busy = ref(false),
  sessionLoading = ref(false),
  status = ref('正在连接'),
  scrollArea = ref()
const config = reactive({ model: '', llm_configured: false, embedding_configured: false })
const toolNames = {
  query_schedule: '查询我的课表',
  get_my_schedules: '查询我的课表',
  search_materials: '检索课程资料',
  list_study_plans: '查看学习计划',
  save_study_plan: '保存学习计划'
}
const prompts = [
  '查看我的课程和每周安排',
  '根据课程资料总结考核要求',
  '结合我的课表制定一份复习计划'
]
let controller
async function scroll() {
  await nextTick()
  if (scrollArea.value) scrollArea.value.scrollTop = scrollArea.value.scrollHeight
}
async function refreshSessions() {
  sessions.value = (await getSessions()).data || []
}
async function newSession() {
  if (busy.value || sessionLoading.value) return
  sessionLoading.value = true
  try {
    const session = (await createSession()).data
    currentId.value = session.id
    messages.value = []
    await refreshSessions()
  } finally {
    sessionLoading.value = false
  }
}
async function selectSession(id) {
  if (busy.value || sessionLoading.value || currentId.value === id) return
  sessionLoading.value = true
  try {
    const rows = (await getMessages(id)).data || []
    currentId.value = id
    messages.value = rows
    await scroll()
  } finally {
    sessionLoading.value = false
  }
}
async function removeSession(id) {
  if (busy.value || sessionLoading.value) return
  if (
    !(await ElMessageBox.confirm('确认删除这段对话？', '删除对话', { type: 'warning' })
      .then(() => true)
      .catch(() => false))
  )
    return
  await deleteSession(id)
  if (currentId.value === id) {
    currentId.value = null
    messages.value = []
  }
  await refreshSessions()
}
function handleKey(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}
function stop() {
  controller?.abort()
}
async function send(prompt) {
  const text = (typeof prompt === 'string' ? prompt : input.value).trim()
  if (!text || busy.value || sessionLoading.value || !config.llm_configured) return
  busy.value = true
  controller = new AbortController()
  let assistant
  try {
    if (!currentId.value) {
      const session = (await createSession()).data
      currentId.value = session.id
    }
    input.value = ''
    messages.value.push({ role: 'user', content: text })
    assistant = reactive({ role: 'assistant', content: '', events: [], sources: [] })
    messages.value.push(assistant)
    status.value = '正在连接课程工具'
    await scroll()
    await streamChat(currentId.value, text, controller.signal, (name, payload) => {
      if (name === 'token') assistant.content += payload.text
      else if (name === 'status') status.value = payload.message
      else if (name === 'sources') assistant.sources = payload.sources
      else if (name === 'tool_start') {
        assistant.events.push(payload)
        status.value = toolNames[payload.name] || '正在调用工具'
      } else if (name === 'tool_end') {
        const event = assistant.events.find((item) => item.id === payload.id)
        if (event) Object.assign(event, payload)
        status.value = '正在整理回答'
      } else if (name === 'error') {
        assistant.content += `\n\n${payload.message}`
        status.value = '生成失败'
      }
      scroll()
    })
  } catch (error) {
    if (error.name === 'AbortError') {
      if (assistant) assistant.content += '\n\n（生成已停止；已执行的工具操作不会撤销。）'
    } else {
      ElMessage.error(error.message || '请求失败')
      if (assistant) assistant.content += `\n\n${error.message || '请求失败'}`
    }
  } finally {
    busy.value = false
    assistant?.events.forEach((event) => {
      if (event.status === 'running') event.status = 'error'
    })
    controller = null
    await refreshSessions()
  }
}
onMounted(async () => {
  Object.assign(config, (await getChatConfig()).data)
  await refreshSessions()
  if (sessions.value.length) await selectSession(sessions.value[0].id)
})
onBeforeUnmount(stop)
</script>

<style scoped>
.assistant-shell {
  display: flex;
  height: calc(100dvh - 112px);
  min-height: 520px;
  background: var(--campus-surface);
  border: 1px solid var(--campus-line);
  border-radius: 14px;
  overflow: hidden;
}
.session-sidebar {
  width: 232px;
  flex-shrink: 0;
  background: var(--campus-canvas);
  border-right: 1px solid var(--campus-line);
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.session-list {
  flex: 1;
  overflow: auto;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  color: var(--campus-muted);
}
.session-item.active {
  background: var(--campus-accent-soft);
  color: var(--campus-accent);
}
.session-item.disabled {
  cursor: default;
}
.session-item > span {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 13px;
}
.sidebar-tip {
  font-size: 11px;
  color: var(--campus-muted);
  text-align: center;
}
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.chat-header {
  padding: 20px 28px;
  border-bottom: 1px solid var(--campus-line);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chat-header h2 {
  font-size: 17px;
  margin-bottom: 5px;
}
.chat-header .muted {
  font-size: 12px;
}
.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px max(24px, calc((100% - 780px) / 2));
}
.chat-welcome {
  max-width: 680px;
  margin: 6vh auto 20px;
}
.welcome-mark {
  width: 60px;
  height: 60px;
  border-radius: 18px;
  background: var(--campus-accent-soft);
  color: var(--campus-accent);
  display: grid;
  place-items: center;
  margin-bottom: 24px;
}
.chat-welcome h1 {
  font-size: clamp(20px, 2.2vw, 28px);
  margin-bottom: 12px;
}
.chat-welcome > p {
  color: var(--campus-muted);
  line-height: 1.8;
}
.suggestions {
  display: grid;
  gap: 12px;
  margin-top: 28px;
}
.suggestions button {
  border: 1px solid var(--campus-line);
  background: var(--campus-surface);
  padding: 17px;
  border-radius: 9px;
  text-align: left;
  color: var(--campus-muted);
  cursor: pointer;
  font: inherit;
  display: flex;
  justify-content: space-between;
}
.suggestions button:hover {
  border-color: var(--el-color-primary-light-5);
  color: var(--campus-accent);
}
.suggestions button:disabled {
  opacity: 0.5;
  cursor: default;
}
.chat-message {
  display: flex;
  gap: 12px;
  margin-bottom: 30px;
}
.message-avatar {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--campus-accent-soft);
  color: var(--campus-accent);
  display: grid;
  place-items: center;
}
.user .message-avatar {
  background: var(--campus-canvas);
  color: var(--campus-muted);
}
.message-body {
  flex: 1;
  min-width: 0;
}
.message-label {
  color: var(--campus-muted);
  font-size: 12px;
  margin: 3px 0 10px;
}
.user-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
}
.tool-events {
  margin-bottom: 14px;
  border: 1px solid var(--campus-line);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--campus-muted);
}
.tool-events > div {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 5px 0;
}
.tool-events small {
  margin-left: auto;
  color: var(--campus-muted);
}
.generation-status {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--campus-muted);
  font-size: 12px;
  margin-top: 12px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--campus-accent);
}
.citation-list {
  margin-top: 16px;
}
.citation {
  background: var(--campus-canvas);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}
.citation p {
  margin-top: 8px;
  color: var(--campus-muted);
  white-space: pre-wrap;
}
.chat-composer {
  padding: 12px 28px 16px;
}
.composer-box {
  border: 1px solid var(--campus-line);
  border-radius: 12px;
  padding: 12px;
}
.composer-box :deep(.el-textarea__inner) {
  box-shadow: none;
  padding: 3px;
}
.composer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}
.composer-bottom > span,
.composer-note {
  color: var(--campus-muted);
  font-size: 11px;
}
.composer-note {
  text-align: center;
  margin-top: 10px;
}
@media (max-width: 900px) {
  .session-sidebar {
    width: 180px;
  }
  .chat-scroll {
    padding: 20px;
  }
}
@media (max-width: 640px) {
  .assistant-shell { flex-direction: column; height: auto; min-height: 0; }
  .session-sidebar {
    width: 100%;
    padding: 10px;
    gap: 8px;
    border-right: 0;
    border-bottom: 1px solid var(--campus-line);
  }
  .session-sidebar > .el-button { align-self: flex-start; }
  .session-list { display: flex; gap: 5px; }
  .session-item { flex: 0 0 auto; max-width: 215px; margin: 0; }
  .sidebar-tip { text-align: start; }
  .chat-scroll { min-height: 240px; max-height: 55dvh; }
  .chat-header,
  .chat-composer {
    padding: 14px;
  }
  .composer-bottom > span {
    display: none;
  }
}
</style>
