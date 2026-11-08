<template>
  <section class="course-assistant">
    <header class="assistant-header">
      <div>
        <h2>课程助手</h2>
        <p>查询个人课表，继续追问课程安排</p>
      </div>
      <div class="header-actions">
        <el-tag v-if="config.model" effect="plain">{{ config.model }}</el-tag>
        <el-button :disabled="busy || !turns.length" @click="turns = []">新对话</el-button>
      </div>
    </header>
    <el-alert v-if="configError" :title="configError" type="error" :closable="false" />
    <el-alert
      v-else-if="!loading && !config.llm_configured"
      title="尚未配置对话模型，请联系管理员。"
      type="warning"
      :closable="false"
    />
    <main ref="scrollArea" class="conversation" aria-label="课程助手对话记录">
      <div v-if="!turns.length" class="welcome">
        <el-icon :size="40"><Reading /></el-icon>
        <h3>从你的课表，开始安排学习</h3>
        <p>回答时查询当前账号的真实排课，支持课程、时间、教师和地点追问。</p>
        <el-button :disabled="!canSend" @click="send('查询我的全部课表')"
          >查询我的全部课表</el-button
        >
      </div>
      <article v-for="turn in turns" :key="turn.id" class="turn">
        <div class="question">
          <strong>你</strong>
          <p>{{ turn.question }}</p>
        </div>
        <div class="answer">
          <strong>课程助手</strong>
          <div v-if="turn.events.length" class="tool-events" aria-label="工具执行过程">
            <div v-for="event in turn.events" :key="event.id">
              <el-icon :class="{ 'is-loading': event.status === 'running' }">
                <Loading v-if="event.status === 'running'" />
                <CircleCheck v-else-if="event.status === 'completed'" />
                <CircleClose v-else />
              </el-icon>
              <span>查询我的课表</span>
              <small>{{ event.summary || toolStatus[event.status] }}</small>
            </div>
          </div>
          <MarkdownContent :content="turn.answer" />
          <p v-if="turn.status === 'running'" class="processing" role="status" aria-live="polite">
            {{ status }}
          </p>
          <el-alert
            v-if="turn.error"
            :title="turn.error"
            :type="turn.status === 'stopped' ? 'info' : 'error'"
            :closable="false"
          />
          <small v-if="turn.status === 'error' || turn.status === 'stopped'" class="excluded"
            >本轮未加入后续对话历史。</small
          >
        </div>
      </article>
    </main>
    <footer class="composer">
      <el-input
        v-model="input"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 5 }"
        resize="none"
        maxlength="6000"
        placeholder="问问我的课表，或继续追问上一个回答…"
        aria-label="课程问题"
        :disabled="busy || !canSend"
        @keydown="onKey"
      />
      <div class="composer-actions">
        <small>将携带 {{ contextCount }} 轮成功问答 · Enter 发送，Shift + Enter 换行</small>
        <el-button v-if="busy" type="danger" plain @click="stop">停止生成</el-button>
        <el-button v-else type="primary" :disabled="!canSend || !input.trim()" @click="send()"
          >发送</el-button
        >
      </div>
      <p class="privacy-note">对话仅保留在当前页面，刷新后清空；只查询当前账号的课表。</p>
    </footer>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Reading, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'
import { getChatConfig } from '@/api/campus'
import { streamQuestion } from '@/api/chat'
import { successfulHistory } from '@/utils/chatHistory'
import { useUser } from '@/utils/user'

const turns = ref([]),
  input = ref(''),
  busy = ref(false),
  loading = ref(true)
const status = ref(''),
  scrollArea = ref(),
  configError = ref('')
const config = reactive({ model: '', llm_configured: false })
const canSend = computed(() => !loading.value && config.llm_configured && !configError.value)
const contextCount = computed(() => successfulHistory(turns.value, input.value).length / 2)
const toolStatus = { running: '进行中', completed: '完成', error: '失败', stopped: '已停止' }
const { userInfo } = useUser()
let controller,
  nextId = 0

async function scroll() {
  await nextTick()
  if (scrollArea.value) scrollArea.value.scrollTop = scrollArea.value.scrollHeight
}
function stop() {
  controller?.abort()
}
function onKey(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}
async function send(prompt) {
  const question = (typeof prompt === 'string' ? prompt : input.value).trim()
  if (!question || busy.value || !canSend.value) return
  const history = successfulHistory(turns.value, question)
  const turn = reactive({
    id: ++nextId,
    question,
    answer: '',
    status: 'running',
    events: [],
    error: ''
  })
  turns.value.push(turn)
  input.value = ''
  busy.value = true
  status.value = '正在连接课程工具'
  controller = new AbortController()
  await scroll()
  try {
    const result = await streamQuestion(question, history, controller.signal, (name, payload) => {
      if (name === 'status') status.value = payload.message
      else if (name === 'token') turn.answer += payload.text
      else if (name === 'tool_start') turn.events.push(payload)
      else if (name === 'tool_end') {
        const event = turn.events.find((item) => item.id === payload.id)
        if (event) Object.assign(event, payload)
      } else if (name === 'error') turn.error = payload.message
      else if (name === 'done' && payload.success) turn.answer = payload.answer
      scroll()
    })
    turn.status = result.success === true ? 'success' : 'error'
    if (turn.status === 'error' && !turn.error) turn.error = '本轮回答未完成，请重试。'
  } catch (error) {
    turn.status = error.name === 'AbortError' ? 'stopped' : 'error'
    turn.error =
      error.name === 'AbortError' ? '已停止生成。' : error.message || '连接中断，请重试。'
  } finally {
    turn.events.forEach((event) => {
      if (event.status === 'running') event.status = turn.status === 'stopped' ? 'stopped' : 'error'
    })
    busy.value = false
    controller = null
    await scroll()
  }
}
watch(
  () => userInfo.value?.id,
  () => {
    stop()
    turns.value = []
    input.value = ''
  }
)
onBeforeUnmount(stop)
onMounted(async () => {
  try {
    Object.assign(config, (await getChatConfig()).data)
  } catch (error) {
    configError.value = error.message || '无法加载对话配置，请刷新后重试。'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.course-assistant {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 112px);
  min-height: 520px;
  background: var(--campus-surface);
  border: 1px solid var(--campus-line);
  border-radius: 14px;
  overflow: hidden;
}
.assistant-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 28px;
  border-bottom: 1px solid var(--campus-line);
}
.assistant-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
}
.assistant-header p,
.privacy-note,
.composer-actions small {
  color: var(--campus-muted);
  font-size: 12px;
}
.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}
.conversation {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 24px 28px;
}
.welcome {
  text-align: center;
  padding: 70px 12px;
  color: var(--campus-muted);
}
.welcome .el-icon {
  color: var(--campus-accent);
}
.welcome h3 {
  color: var(--campus-text);
  margin: 18px 0 12px;
}
.welcome p {
  margin-bottom: 22px;
  line-height: 1.8;
}
.turn {
  margin-bottom: 30px;
}
.question {
  background: var(--campus-canvas);
  padding: 14px 18px;
  border-radius: 10px;
  margin-bottom: 18px;
}
.question p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
  margin: 6px 0 0;
}
.question strong,
.answer > strong {
  display: block;
  color: var(--campus-muted);
  font-size: 12px;
  margin-bottom: 10px;
}
.answer {
  padding: 0 6px;
}
.tool-events {
  border: 1px solid var(--campus-line);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  color: var(--campus-muted);
}
.tool-events > div {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px 0;
  font-size: 12px;
}
.tool-events small {
  margin-left: auto;
}
.processing {
  color: var(--campus-accent);
  font-size: 13px;
  padding: 8px 0;
}
.excluded {
  display: block;
  margin-top: 8px;
  color: var(--campus-muted);
}
.composer {
  padding: 16px 24px;
  border-top: 1px solid var(--campus-line);
}
.composer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.privacy-note {
  text-align: center;
  margin: 10px 0 0;
}
@media (max-width: 640px) {
  .assistant-header,
  .conversation,
  .composer {
    padding: 16px;
  }
  .header-actions .el-tag {
    display: none;
  }
  .composer-actions small {
    font-size: 10px;
  }
  .welcome {
    padding: 40px 0;
  }
}
</style>
