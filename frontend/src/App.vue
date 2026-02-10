<template>
  <div class="notebook-container">
    <el-container class="full-height">
      <el-aside width="300px" class="aside-sources">
        <div class="aside-header">
          <span class="header-title">来源</span>
          <el-button type="primary" size="small" circle @click="uploadDialogVisible = true">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>

        <el-scrollbar class="aside-scroll">
          <div class="source-group">
            <div class="group-label">📌 系统默认资料 ({{ defaultSources.length }})</div>
            <div v-for="item in defaultSources" :key="item.id" class="source-card fixed">
              <el-icon><Collection /></el-icon>
              <span class="name">{{ item.name }}</span>
            </div>
          </div>

          <div class="source-group">
            <div class="group-label">👤 我的上传 ({{ userSources.length }})</div>
            <el-empty v-if="userSources.length === 0" description="暂无个人资料" :image-size="40" />
            <div v-for="item in userSources" :key="item.id" class="source-card user-added">
              <el-icon><Document /></el-icon>
              <span class="name">{{ item.name }}</span>
              <el-button link type="danger" icon="Delete" @click="handleDeleteSource(item.id)" />
            </div>
          </div>
        </el-scrollbar>
      </el-aside>

      <el-main class="main-chat">
        <div class="chat-header">
          <div class="chat-info">
            <el-icon><ChatLineRound /></el-icon>
            <span>QZhou-7B 知识库对话</span>
          </div>
        </div>

        <div class="chat-viewport" ref="chatRef">
          <div v-for="(msg, i) in history" :key="i" :class="['msg-row', msg.role]">
            <div class="avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
            <div class="content-box">
              <div class="bubble" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <div v-if="loading && !history[history.length-1].content" class="typing">
            <el-icon class="is-loading"><Loading /></el-icon> 正在检索并思考...
          </div>
        </div>

        <div class="input-panel">
          <div class="input-container">
            <el-input
              v-model="userInput"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="向你的知识库提问..."
              @keyup.enter.prevent="handleSend"
            />
            <el-button type="primary" :loading="loading" @click="handleSend" circle>
              <el-icon><Top /></el-icon>
            </el-button>
          </div>
        </div>
      </el-main>

      <el-aside width="380px" class="aside-evidence">
        <div class="aside-header">📖 证据链溯源</div>
        <el-scrollbar class="aside-scroll">
          <el-empty v-if="evidences.length === 0" description="暂无引用内容" />
          <div v-for="(ev, idx) in evidences" :key="idx" class="evidence-card">
            <div class="ev-top">
              <el-tag size="small" type="warning" effect="dark">引用 #{{ idx + 1 }}</el-tag>
              <span class="ev-score" v-if="ev.score">相关度: {{ ev.score }}</span>
            </div>
            <div class="ev-content">{{ ev.content }}</div>
            <div class="ev-footer">
              <span class="source-name">📄 {{ ev.source }}</span>
              <span class="page-num">P{{ ev.pages }}</span>
            </div>
          </div>
        </el-scrollbar>
      </el-aside>
    </el-container>

    <el-dialog v-model="uploadDialogVisible" title="添加来源" width="450px" center>
      <el-upload
        class="upload-demo"
        drag
        action="http://localhost:8000/api/upload"
        multiple
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF/Markdown 格式，上传后将自动进行向量化</div>
        </template>
      </el-upload>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()
const userInput = ref('')
const loading = ref(false)
const uploadDialogVisible = ref(false)
const chatRef = ref(null)

// --- 数据状态 ---
const defaultSources = ref([
  { id: 's1', name: '2025级大数据培养方案.pdf' },
  { id: 's2', name: '工程认证通用标准.md' }
])
const userSources = ref([])
const history = ref([{ role: 'assistant', content: '你好！我已经准备好分析你的资料了。请在左侧添加或选择来源，然后开始提问。' }])
const evidences = ref([])

// --- 接口函数预留 ---
const handleUploadSuccess = (res) => {
  // TODO: 后端应返回文件 ID 和名称
  userSources.value.push({ id: res.id, name: res.filename })
  uploadDialogVisible.value = false
}

const handleUploadError = () => {
  // 仅做演示，实际应显示错误
  userSources.value.push({ id: Date.now(), name: '模拟上传文件.pdf' })
  uploadDialogVisible.value = false
}

const handleDeleteSource = (id) => {
  // TODO: 调用 DELETE /api/sources/{id}
  userSources.value = userSources.value.filter(s => s.id !== id)
}

const renderMarkdown = (t) => md.render(t || '')

const handleSend = async () => {
  if (!userInput.value.trim() || loading.value) return
  
  const query = userInput.value
  history.value.push({ role: 'user', content: query })
  userInput.value = ''
  loading.value = true
  evidences.value = []
  
  history.value.push({ role: 'assistant', content: '' })
  const lastIndex = history.value.length - 1

  try {
    const response = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: query, top_k: 4 })
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let hasMeta = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      
      if (!hasMeta && chunk.includes('---METADATA_SEPARATOR---')) {
        const parts = chunk.split('---METADATA_SEPARATOR---')
        evidences.value = JSON.parse(parts[0]).evidence
        history.value[lastIndex].content += parts[1]
        hasMeta = true
      } else {
        history.value[lastIndex].content += chunk
      }
      nextTick(() => { chatRef.value.scrollTop = chatRef.value.scrollHeight })
    }
  } catch (err) {
    history.value[lastIndex].content = '❌ 无法连接到服务器，请检查后端状态。'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.notebook-container { height: 100vh; background-color: #fcfcfd; }
.full-height { height: 100%; }

/* 通用头部样式 */
.aside-header { 
  height: 64px; padding: 0 20px; display: flex; align-items: center; 
  justify-content: space-between; border-bottom: 1px solid #f0f0f2;
  font-weight: 600; font-size: 16px; background: #fff;
}

/* 左侧来源栏 */
.aside-sources { background: #f8f9fa; border-right: 1px solid #e9ecef; display: flex; flex-direction: column; }
.source-group { padding: 16px; }
.group-label { font-size: 12px; color: #868e96; font-weight: 700; margin-bottom: 12px; text-transform: uppercase; }
.source-card { 
  background: #fff; padding: 10px 12px; border-radius: 8px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 10px; font-size: 13px;
  border: 1px solid transparent; cursor: pointer; transition: 0.2s;
}
.source-card:hover { border-color: #4dabf7; background: #f1f3f5; }
.source-card .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 中间对话栏 */
.main-chat { padding: 0; display: flex; flex-direction: column; background: #fff; }
.chat-header { height: 64px; border-bottom: 1px solid #f0f0f2; display: flex; align-items: center; padding: 0 30px; font-weight: 600; }
.chat-viewport { flex: 1; overflow-y: auto; padding: 40px 10%; }
.msg-row { display: flex; gap: 20px; margin-bottom: 40px; }
.msg-row.user { flex-direction: row-reverse; }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: #e9ecef; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }
.user .avatar { background: #339af0; color: #fff; }
.content-box { max-width: 80%; }
.bubble { line-height: 1.8; font-size: 15px; color: #212529; }
.user .bubble { background: #f1f3f5; padding: 12px 20px; border-radius: 18px; }

/* 输入框 */
.input-panel { padding: 20px 10% 40px; }
.input-container { 
  background: #fff; border: 1px solid #dee2e6; border-radius: 28px;
  padding: 8px 16px; display: flex; align-items: center; gap: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}
.input-container :deep(.el-textarea__inner) { border: none; box-shadow: none; padding: 8px 0; resize: none; }

/* 右侧证据栏 */
.aside-evidence { background: #fff; border-left: 1px solid #e9ecef; }
.evidence-card { margin: 16px; padding: 16px; border: 1px solid #f1f3f5; border-radius: 10px; background: #fdfdfe; }
.ev-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.ev-score { font-size: 11px; color: #868e96; font-family: monospace; }
.ev-content { font-size: 13px; color: #495057; line-height: 1.6; margin-bottom: 14px; }
.ev-footer { display: flex; justify-content: space-between; font-size: 11px; color: #adb5bd; border-top: 1px solid #f8f9fa; padding-top: 10px; }
</style>