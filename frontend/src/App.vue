<template>
  <div class="app-layout" @mousemove="handleMouseMove" @mouseup="handleMouseUp">
    
    <div class="panel left-panel" :style="{ width: leftWidth + 'px' }">
      <div class="panel-header">
        <span class="header-title">📚 知识库</span>
        <el-upload
          class="upload-wrapper"
          action="http://localhost:8000/api/upload"
          name="file"
          :show-file-list="false"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
          :before-upload="beforeUpload"
        >
          <el-button type="primary" link size="small">
            <el-icon :size="14"><Plus /></el-icon>
          </el-button>
        </el-upload>
      </div>

      <el-scrollbar class="panel-body">
        <div class="source-group" v-if="systemSources.length > 0">
          <div class="group-label">🏛️ 制度文件 ({{ systemSources.length }})</div>
          <div 
            v-for="item in systemSources" 
            :key="item.id" 
            class="source-item"
            :class="{ active: selectedIds.includes(item.id) }"
            @click="toggleSelection(item.id)"
          >
            <el-checkbox v-model="selectedIds" :label="item.id" @click.stop class="mini-checkbox"/>
            <el-icon class="file-icon"><School /></el-icon>
            <span class="file-name" :title="item.name">{{ item.name }}</span>
          </div>
        </div>

        <div class="source-group">
          <div class="group-label">👤 我的资料 ({{ userSources.length }})</div>
          <el-empty v-if="userSources.length === 0" description="暂无文件" :image-size="30" />
          
          <div 
            v-for="item in userSources" 
            :key="item.id" 
            class="source-item"
            :class="{ 
              active: selectedIds.includes(item.id) && !item.isUploading,
              'is-processing': item.isUploading 
            }"
            @click="!item.isUploading && toggleSelection(item.id)"
          >
            <el-checkbox 
              v-model="selectedIds" 
              :label="item.id" 
              @click.stop 
              class="mini-checkbox"
              :disabled="item.isUploading"
              :style="{ visibility: item.isUploading ? 'hidden' : 'visible' }"
            />
            
            <el-icon class="file-icon custom-spin" v-if="item.isUploading"><Loading /></el-icon>
            <el-icon class="file-icon" v-else><Document /></el-icon>
            
            <span class="file-name" :title="item.name">{{ item.name }}</span>
            
            <el-icon class="del-icon" @click.stop="handleDeleteSource(item.id)" v-if="!item.isUploading"><Delete /></el-icon>
          </div>

        </div>
      </el-scrollbar>

      <div class="panel-footer">
        <span v-if="selectedIds.length === 0">全库模式</span>
        <span v-else>已选 {{ selectedIds.length }} 个</span>
        <el-button v-if="selectedIds.length > 0" link type="primary" size="small" @click="selectedIds = []">清空</el-button>
      </div>
    </div>

    <div class="resizer" @mousedown="startResize($event, 'left')"></div>

    <div class="panel center-panel">
      <div class="chat-header">
        <div class="chat-title">
          <el-icon><ChatLineRound /></el-icon> Notebook RAG
          <el-tag v-if="selectedIds.length > 0" size="small" effect="plain" round class="ml-2 mini-tag">
            范围: {{ selectedIds.length }}
          </el-tag>
        </div>
      </div>

      <div class="chat-viewport" ref="chatRef">
        <div v-for="(msg, i) in history" :key="i" :class="['msg-row', msg.role]">
          <div class="avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
          <div class="msg-content">
            <div class="bubble markdown-body" v-html="renderMarkdown(msg.content)"></div>
          </div>
        </div>
        
        <div v-if="thinking" class="msg-row assistant">
          <div class="avatar">AI</div>
          <div class="msg-content">
            <div class="bubble thinking">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <div class="gemini-input-wrapper">
          <el-input
            v-model="userInput"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 6 }"
            placeholder="问点什么..."
            @keydown.enter.exact.prevent="handleSend"
            class="gemini-textarea"
          />
          <div class="send-btn-box">
             <el-button 
               type="primary" 
               :loading="thinking" 
               @click="handleSend" 
               circle 
               class="gemini-send-btn"
               :disabled="!userInput.trim() && !thinking"
             >
               <el-icon v-if="!thinking"><Top /></el-icon>
             </el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="resizer" @mousedown="startResize($event, 'right')"></div>

    <div class="panel right-panel" :style="{ width: rightWidth + 'px' }">
      
      <template v-if="!isPdfMode">
        <div class="panel-header">
          <span class="header-title">📖 引用来源</span>
          <el-tag type="info" size="small" round class="mini-tag">{{ evidences.length }}</el-tag>
        </div>
        <el-scrollbar class="panel-body bg-gray">
          <el-empty v-if="evidences.length === 0" description="暂无引用" :image-size="40" />
          
          <div 
            v-for="(ev, idx) in evidences" 
            :key="idx" 
            class="evidence-card clickable"
            @click="openPdf(ev)"
          >
            <div class="ev-meta">
              <span class="idx">#{{ idx + 1 }}</span>
              <span class="score">{{ (ev.score * 100).toFixed(0) }}% 匹配</span>
            </div>
            <div class="ev-text">{{ ev.content }}</div>
            <div class="ev-source">
              <el-icon><Document /></el-icon>
              <span class="trunc-text">{{ ev.source }}</span>
              <span class="page-tag">P{{ ev.pages }} ↗</span>
            </div>
          </div>
        </el-scrollbar>
      </template>

      <template v-else>
        <div class="notebooklm-header">
           <span class="source-label">来源</span>
           <div class="header-main-row">
             <h2 class="doc-title trunc-text" :title="currentPdfName">{{ currentPdfName }}</h2>
             <div class="close-btn" @click="closePdf">
               <el-icon><Close /></el-icon>
             </div>
           </div>
        </div>
        
        <div class="notebooklm-body">
          <VuePdfApp
            :pdf="pdfUrl"
            :page-number="currentPdfPage"
            theme="light" 
            :config="pdfConfig"
            class="clean-pdf-viewer"
            :key="pdfUrl"
          />
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import { ElMessage } from 'element-plus'
import { Plus, Document, Delete, ChatLineRound, Top, Loading, School, Close } from '@element-plus/icons-vue' 

import VuePdfApp from "vue3-pdf-app";
import "vue3-pdf-app/dist/icons/main.css";

const md = new MarkdownIt({ html: true, linkify: true })

const leftWidth = ref(240)
const rightWidth = ref(400) 
const isResizing = ref(null)

const allSources = ref([])
const selectedIds = ref([])
const userInput = ref('')
const thinking = ref(false)
const chatRef = ref(null)
const evidences = ref([])
const history = ref([{ role: 'assistant', content: '你好！请在左侧上传或勾选文件，然后开始提问。' }])

const isPdfMode = ref(false)
const pdfUrl = ref('') 
const currentPdfName = ref('')
const currentPdfPage = ref(1)

const pdfConfig = ref({
  sidebar: false, 
  secondaryToolbar: false, 
  toolbar: false, 
  footer: false 
})

const systemSources = computed(() => allSources.value.filter(s => s.category === 'system'))
const userSources = computed(() => allSources.value.filter(s => s.category === 'user'))

const startResize = (e, side) => {
  isResizing.value = side
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}
const handleMouseMove = (e) => {
  if (!isResizing.value) return
  if (isResizing.value === 'left') {
    const w = e.clientX
    if (w > 180 && w < 400) leftWidth.value = w
  } else if (isResizing.value === 'right') {
    const w = window.innerWidth - e.clientX
    if (w > 300 && w < 900) rightWidth.value = w
  }
}
const handleMouseUp = () => { isResizing.value = null; document.body.style.cursor = ''; document.body.style.userSelect = '' }

const fetchSources = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/sources')
    if (res.ok) allSources.value = await res.json()
  } catch (e) { ElMessage.error('连接后端失败') }
}

// 🟢 修改点 1：上传前，将要上传的文件变成带有 isUploading 标记的占位对象
const beforeUpload = (file) => { 
  allSources.value.push({
    id: `temp-${file.name}-${Date.now()}`, // 临时ID
    name: file.name,
    category: 'user',
    isUploading: true // 开启加载状态
  })
  return true 
}

// 🟢 修改点 2：上传成功后，找到那个占位对象，更新为正式数据
const handleUploadSuccess = (res, uploadFile) => {
  const index = allSources.value.findIndex(s => s.name === uploadFile.name && s.isUploading)
  if (index !== -1) {
    // 替换为正式数据
    allSources.value[index].id = res.id
    allSources.value[index].isUploading = false
    selectedIds.value.push(res.id)
  } else {
    // 兜底逻辑
    allSources.value.push({ id: res.id, name: res.name, category: 'user' })
    selectedIds.value.push(res.id)
  }
  ElMessage.success('文档解析完成，已加入知识库')
}

// 🟢 修改点 3：上传失败，删除对应的占位对象
const handleUploadError = (err, uploadFile) => {
  allSources.value = allSources.value.filter(s => !(s.name === uploadFile.name && s.isUploading))
  ElMessage.error('上传失败，请检查后端日志')
}

const handleDeleteSource = async (id) => {
  try {
    const res = await fetch(`http://localhost:8000/api/sources/${id}`, { method: 'DELETE' })
    if (res.ok) {
      allSources.value = allSources.value.filter(s => s.id !== id)
      selectedIds.value = selectedIds.value.filter(sid => sid !== id)
    }
  } catch (e) {}
}

const handleSend = async () => {
  if (!userInput.value.trim() || thinking.value) return
  const query = userInput.value
  history.value.push({ role: 'user', content: query })
  userInput.value = ''
  thinking.value = true
  evidences.value = []
  if (isPdfMode.value) closePdf()
  nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight })

  try {
    const historyPayload = history.value.slice(0, -1).map(m => ({ role: m.role, content: m.content }))
    const res = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: query, top_k: 4, source_filter: selectedIds.value, history: historyPayload })
    })
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    history.value.push({ role: 'assistant', content: '' })
    let lastMsg = history.value[history.value.length - 1]
    let buffer = '', hasMeta = false
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      if (!hasMeta && buffer.includes('---METADATA_SEPARATOR---')) {
        const parts = buffer.split('---METADATA_SEPARATOR---')
        try { evidences.value = JSON.parse(parts[0]).evidence || [] } catch (e) {}
        buffer = parts[1] || ''
        hasMeta = true
      }
      if (hasMeta || (!buffer.includes('---METADATA_SEPARATOR---') && buffer.length > 500)) {
        hasMeta = true
        lastMsg.content = buffer
        if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
      }
    }
  } catch (e) { history.value.push({ role: 'assistant', content: '❌ 请求失败' }) } finally { thinking.value = false }
}

const openPdf = (ev) => {
  const filename = ev.source
  let page = 1

  if (Array.isArray(ev.pages) && ev.pages.length > 0) {
    page = ev.pages[0]
  } else if (typeof ev.pages === 'number') {
    page = ev.pages
  } else if (typeof ev.pages === 'string') {
    const parsed = parseInt(ev.pages)
    if (!isNaN(parsed)) page = parsed
  }
  
  if (page < 1) page = 1

  currentPdfName.value = filename
  currentPdfPage.value = page
  pdfUrl.value = `http://localhost:8000/api/view/${encodeURIComponent(filename)}`
  isPdfMode.value = true
}

const closePdf = () => { isPdfMode.value = false; pdfUrl.value = '' }

const toggleSelection = (id) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx > -1) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}
const renderMarkdown = (t) => md.render(t || '')
onMounted(fetchSources)
</script>

<style scoped>
/* 1. 布局 (固定) */
.app-layout {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; background-color: #fcfcfd;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 12px; color: #2c3e50; overflow: hidden;
}

/* 2. 面板基础 */
.panel { display: flex; flex-direction: column; background: #fff; height: 100%; }
.center-panel { flex: 1; min-width: 300px; background: #fff; }
.panel-header {
  height: 42px; border-bottom: 1px solid #ebEEF5; display: flex; align-items: center;
  padding: 0 10px; justify-content: space-between; flex-shrink: 0; background: #fdfdfd;
}
.header-title { font-weight: 600; font-size: 13px; }
.panel-body { flex: 1; overflow-y: auto; }
.bg-gray { background-color: #fafafa; }

/* 拖拽条 */
.resizer { width: 1px; background: #e0e0e0; cursor: col-resize; z-index: 10; flex-shrink: 0; position: relative; }
.resizer::after { content: ''; position: absolute; left: -3px; right: -3px; top: 0; bottom: 0; z-index: 1; }
.resizer:hover { background: #409eff; width: 2px; }

/* 3. 左侧样式 */
.group-label { padding: 10px 10px 4px; font-size: 11px; color: #909399; font-weight: 600; }
.source-item {
  display: flex; align-items: center; padding: 0 10px; cursor: pointer; height: 28px; font-size: 12px;
}
.source-item:hover { background: #f2f6fc; }
.source-item.active { background: #ecf5ff; color: #409eff; }

/* 🟢 修改点：处理中的样式变灰 */
.source-item.is-processing { opacity: 0.6; cursor: wait; background: transparent; }

.file-icon { margin-right: 6px; color: #909399; font-size: 13px; }
.file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.del-icon { display: none; color: #f56c6c; padding: 4px; font-size: 12px; }
.source-item:hover .del-icon { display: block; }
.mini-checkbox { margin-right: 4px; transform: scale(0.8); }
.panel-footer {
  height: 32px; border-top: 1px solid #ebEEF5; display: flex; align-items: center;
  justify-content: space-between; padding: 0 10px; font-size: 11px; color: #909399; background: #fafafa;
}

@keyframes rotating {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.custom-spin {
  animation: rotating 2s linear infinite;
  color: #409eff; 
}

/* 4. 中间聊天样式 */
.chat-header {
  height: 42px; border-bottom: 1px solid #ebEEF5; display: flex; align-items: center;
  justify-content: center; font-weight: 600; font-size: 13px; background: #fff;
}
.chat-viewport { flex: 1; overflow-y: auto; padding: 15px; }
.msg-row { display: flex; margin-bottom: 16px; gap: 8px; }
.msg-row.user { flex-direction: row-reverse; }
.avatar {
  width: 24px; height: 24px; background: #f0f2f5; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: bold; color: #606266; flex-shrink: 0;
}
.msg-row.user .avatar { background: #409eff; color: #fff; }
.bubble {
  max-width: 100%; padding: 6px 10px; border-radius: 6px;
  line-height: 1.5; font-size: 12px;
}
.msg-row.user .bubble { background: #ecf5ff; color: #409eff; }

/* 5. 输入框区域 */
.input-area {
  padding: 0 15% 30px; 
  background: linear-gradient(to bottom, rgba(255,255,255,0), #fff 40%);
  z-index: 10;
  display: flex;
  justify-content: center;
}

.gemini-input-wrapper {
  width: 100%;
  max-width: 800px;
  position: relative;
  display: flex;
  align-items: flex-end; 
  background-color: #f0f4f9; 
  border-radius: 28px;
  padding: 12px 16px;
  border: 1px solid transparent;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.gemini-input-wrapper:focus-within {
  background-color: #fff;
  border-color: #d3e3fd; 
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.gemini-textarea {
  flex: 1;
  margin-right: 8px;
}

.gemini-textarea :deep(.el-textarea__inner) {
  background: transparent !important;
  box-shadow: none !important;
  border: none !important;
  padding: 4px 0; 
  font-size: 15px;
  line-height: 24px;
  color: #1f1f1f;
  resize: none;
  min-height: 32px !important; 
  height: 32px;
}

.gemini-textarea :deep(.el-textarea__inner)::-webkit-scrollbar { width: 0; }

.send-btn-box {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gemini-send-btn {
  width: 32px; height: 32px; font-size: 16px;
  transition: all 0.2s; background-color: transparent; color: #1f1f1f; border: none;
}

.gemini-input-wrapper:focus-within .gemini-send-btn,
.gemini-send-btn:not(.is-disabled) {
  background-color: #0b57d0; color: #fff;
}

.gemini-send-btn:hover {
  transform: scale(1.05); box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}
.gemini-send-btn.is-disabled { background-color: transparent; color: #ccc; }

/* 5. 右侧列表样式 */
.mini-tag { transform: scale(0.9); }
.evidence-card {
  background: #fff; border: 1px solid #ebEEF5; border-radius: 4px;
  padding: 8px; margin: 8px; transition: all 0.1s;
}
.evidence-card:hover {
  transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,0.04); border-color: #c6e2ff;
}
.ev-meta { display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 4px; color: #909399; }
.score { color: #67c23a; font-family: monospace; }
.ev-text {
  font-size: 11px; line-height: 1.4; color: #606266; margin-bottom: 6px;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
}
.ev-source {
  display: flex; align-items: center; gap: 4px; font-size: 10px; color: #909399;
  padding-top: 4px; border-top: 1px solid #f2f6fc;
}
.trunc-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px; }
.page-tag { margin-left: auto; background: #fdf6ec; color: #e6a23c; padding: 1px 3px; border-radius: 2px; }

/* 6. 右侧：仿 NotebookLM 头部 */
.notebooklm-header {
  padding: 16px 20px 10px; background: #fff;
  display: flex; flex-direction: column; gap: 4px;
  border-bottom: 1px solid transparent; 
}
.source-label { font-size: 11px; color: #5f6368; font-weight: 500; }
.header-main-row { display: flex; justify-content: space-between; align-items: center; }
.doc-title {
  font-size: 18px; font-weight: 500; color: #1f1f1f; margin: 0; padding: 0;
  line-height: 1.2;
}
.close-btn {
  cursor: pointer; width: 28px; height: 28px; border-radius: 50%; background: #f1f3f4;
  display: flex; align-items: center; justify-content: center; color: #5f6368;
}
.close-btn:hover { background: #e8eaed; color: #202124; }

/* 7. 右侧：纯净文档 */
.notebooklm-body {
  flex: 1; overflow: hidden; background: #fff; 
  display: flex; flex-direction: column;
}

.clean-pdf-viewer { background: #fff !important; }

:deep(.pdf-app-container) { background-color: #fff !important; }
:deep(#viewerContainer) { background-color: #fff !important; padding: 0 !important; }
:deep(.page) {
  margin: 0 auto 20px !important; box-shadow: none !important; 
  border: none !important; border-bottom: 1px solid #f1f3f4 !important; 
}

:deep(#viewerContainer::-webkit-scrollbar) { width: 8px; }
:deep(#viewerContainer::-webkit-scrollbar-thumb) { background-color: #dadce0; border-radius: 4px; }

:deep(.el-checkbox__label) { display: none; }
:deep(.markdown-body p) { margin-bottom: 6px; }
</style>