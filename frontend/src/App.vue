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

      <div class="chat-viewport" ref="chatRef" @click="handleCitationClick">
        <div v-for="(msg, i) in history" :key="i" :class="['msg-row', msg.role]" :data-msg-index="i">
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
      
      <template v-if="rightPanelMode === 'list'">
        <div class="panel-header">
          <span class="header-title">📖 引用来源</span>
          <el-tag type="info" size="small" round class="mini-tag">{{ currentEvidences.length }}</el-tag>
        </div>
        <el-scrollbar class="panel-body bg-gray">
          <el-empty v-if="currentEvidences.length === 0" description="AI 暂未使用引用" :image-size="40" />
          
          <div 
            v-for="ev in currentEvidences" 
            :key="ev.visualIndex" 
            class="evidence-card clickable"
            @click="openCitationDetail(ev)" 
          >
            <div class="ev-meta">
              <span class="idx">#{{ ev.visualIndex }}</span>
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

      <template v-else-if="rightPanelMode === 'detail'">
        <div class="notebooklm-header">
           <span class="source-label">来源原文 (高亮)</span>
           <div class="header-main-row">
             <h2 class="doc-title trunc-text" :title="currentCitation.source">{{ currentCitation.source }}</h2>
             <div class="close-btn" @click="rightPanelMode = 'list'">
               <el-icon><Close /></el-icon>
             </div>
           </div>
           <div class="citation-meta-tags">
             <el-tag size="small" type="warning" effect="light">P{{ currentCitation.pages }}</el-tag>
             <el-tag size="small" type="info" effect="light">检索原标号: [{{ currentCitation.index }}]</el-tag>
           </div>
        </div>
        
        <el-scrollbar class="notebooklm-body citation-detail-body">
          
          <div class="debug-panel">
            <div class="debug-title">🛠️ [调试] 1. 原始切片内容 (Raw Chunk)：</div>
            <pre class="debug-code">{{ currentCitation.content }}</pre>
            
            <div class="debug-title" style="margin-top: 10px;">🛠️ [调试] 2. 正则清洗后的切片 (Clean Chunk)：</div>
            <pre class="debug-code">{{ debugCleanChunk(currentCitation.content) }}</pre>
          </div>

          <div class="markdown-body custom-md" v-html="renderHighlightedMarkdown(currentCitation.full_content || currentCitation.content, currentCitation.content)"></div>
        </el-scrollbar>
      </template>

      <template v-else-if="rightPanelMode === 'pdf'">
        <div class="notebooklm-header">
           <span class="source-label">来源</span>
           <div class="header-main-row">
             <h2 class="doc-title trunc-text" :title="currentPdfName">{{ currentPdfName }}</h2>
             <div class="close-btn" @click="rightPanelMode = 'list'">
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

const history = ref([{ role: 'assistant', content: '你好！请在左侧上传或勾选文件，然后开始提问。', evidences: [] }])
const rightPanelMode = ref('list') 
const currentCitation = ref(null) 

const pdfUrl = ref('') 
const currentPdfName = ref('')
const currentPdfPage = ref(1)
const pdfConfig = ref({ sidebar: false, secondaryToolbar: false, toolbar: false, footer: false })

const systemSources = computed(() => allSources.value.filter(s => s.category === 'system'))
const userSources = computed(() => allSources.value.filter(s => s.category === 'user'))

// 核心计算属性：动态过滤与重排序右侧卡片列表
const currentEvidences = computed(() => {
  const lastMsg = history.value.slice().reverse().find(m => m.role === 'assistant' && m.evidences && m.evidences.length > 0)
  if (!lastMsg || !lastMsg.content) return []

  const matches = [...lastMsg.content.matchAll(/\[(\d+)\]/g)]
  const seen = new Set()
  const orderedOriginalIndexes = []
  
  for (const match of matches) {
    const origIdx = parseInt(match[1])
    if (!seen.has(origIdx)) {
      seen.add(origIdx)
      orderedOriginalIndexes.push(origIdx)
    }
  }

  if (orderedOriginalIndexes.length === 0) {
     return lastMsg.evidences.map((ev, i) => ({ ...ev, visualIndex: ev.index || (i+1) }))
  }

  return orderedOriginalIndexes.map((origIdx, i) => {
    const ev = lastMsg.evidences.find(e => e.index === origIdx)
    if (ev) {
      return { ...ev, visualIndex: i + 1 }
    }
    return null
  }).filter(Boolean)
})


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

const beforeUpload = (file) => { 
  allSources.value.push({ id: `temp-${file.name}-${Date.now()}`, name: file.name, category: 'user', isUploading: true })
  return true 
}

const handleUploadSuccess = (res, uploadFile) => {
  const index = allSources.value.findIndex(s => s.name === uploadFile.name && s.isUploading)
  if (index !== -1) {
    allSources.value[index].id = res.id; allSources.value[index].isUploading = false; selectedIds.value.push(res.id)
  } else {
    allSources.value.push({ id: res.id, name: res.name, category: 'user' }); selectedIds.value.push(res.id)
  }
  ElMessage.success('文档解析完成，已加入知识库')
}

const handleUploadError = (err, uploadFile) => {
  allSources.value = allSources.value.filter(s => !(s.name === uploadFile.name && s.isUploading))
  ElMessage.error('上传失败，请检查后端日志')
}

const handleDeleteSource = async (id) => {
  try {
    const res = await fetch(`http://localhost:8000/api/sources/${id}`, { method: 'DELETE' })
    if (res.ok) {
      allSources.value = allSources.value.filter(s => s.id !== id); selectedIds.value = selectedIds.value.filter(sid => sid !== id)
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
  rightPanelMode.value = 'list'
  
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
    
    history.value.push({ role: 'assistant', content: '', evidences: [] })
    let lastMsg = history.value[history.value.length - 1]
    
    let buffer = '', hasMeta = false
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      
      if (!hasMeta && buffer.includes('---METADATA_SEPARATOR---')) {
        const parts = buffer.split('---METADATA_SEPARATOR---')
        try { 
          const evs = JSON.parse(parts[0]).evidence || []
          evidences.value = evs 
          lastMsg.evidences = evs 
        } catch (e) {
          console.error("解析元数据 JSON 失败:", e)
        }
        
        buffer = parts.slice(1).join('---METADATA_SEPARATOR---') || ''
        hasMeta = true 
      }
      
      if (hasMeta) {
        lastMsg.content = buffer
        if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
      }
    }
  } catch (e) { history.value.push({ role: 'assistant', content: '❌ 请求失败' }) } finally { thinking.value = false }
}

const renderMarkdown = (t) => {
  if (!t) return ''
  const citationMap = new Map()
  let seq = 1
  
  const htmlWithCitations = t.replace(/\[(\d+)\]/g, (match, p1) => {
    const origIdx = parseInt(p1)
    if (!citationMap.has(origIdx)) {
      citationMap.set(origIdx, seq++) 
    }
    const visualIdx = citationMap.get(origIdx)
    return `<sup class="citation-btn" data-orig-index="${origIdx}">[${visualIdx}]</sup>`
  })
  
  return md.render(htmlWithCitations)
}

// 提供给面板调试用的清洗函数
const debugCleanChunk = (chunkText) => {
  if (!chunkText) return ''
  return chunkText.replace(/^(?:\s*【[\s\S]*?】\s*)+/, '').trim()
}


// 🟢 核心功能 2：终极抗干扰高亮算法（提取纯核心文本进行降维映射匹配）
const renderHighlightedMarkdown = (fullText, chunkText) => {
  if (!fullText) return md.render(chunkText || '')
  if (!chunkText) return md.render(fullText)

  // 1. 除脏：切除【来源文档...】等拼接前缀
  let pureChunk = chunkText.replace(/^(?:\s*【[\s\S]*?】\s*)+/, '').trim()
  if (!pureChunk) pureChunk = chunkText

  // 2. 原生精确匹配兜底（inline 插入，不用换行包裹避免破坏结构）
  if (fullText.includes(pureChunk)) {
    const idx = fullText.indexOf(pureChunk)
    const before = fullText.substring(0, idx)
    const after = fullText.substring(idx + pureChunk.length)
    return md.render(`${before}<mark class="chunk-highlight">${pureChunk}</mark>${after}`)
  }

  // 3. 构建核心字映射表（只保留汉字、字母、数字，彻底无视标点/空格/换行/Markdown符号）
  const isCoreChar = (char) => /[\u4e00-\u9fa5a-zA-Z0-9]/.test(char)

  const fullMap = []
  let fullCore = ''
  for (let i = 0; i < fullText.length; i++) {
    if (isCoreChar(fullText[i])) {
      fullCore += fullText[i]
      fullMap.push(i)
    }
  }

  let chunkCore = ''
  for (let i = 0; i < pureChunk.length; i++) {
    if (isCoreChar(pureChunk[i])) chunkCore += pureChunk[i]
  }

  if (chunkCore.length < 10) return md.render(fullText)

  // 4. 用头部/尾部各取 min(15, 一半) 个核心字定位，避免极短 chunk 时头尾重叠
  const HEAD_LEN = Math.min(15, Math.floor(chunkCore.length / 2))
  const TAIL_LEN = Math.min(15, Math.floor(chunkCore.length / 2))
  let headStr = chunkCore.substring(0, HEAD_LEN)
  let tailStr = chunkCore.substring(chunkCore.length - TAIL_LEN)

  let startCoreIdx = fullCore.indexOf(headStr)

  // 容错：前 HEAD_LEN 字对不上时，跳过前 10 个核心字重试
  if (startCoreIdx === -1 && chunkCore.length > 30) {
    const altHead = chunkCore.substring(10, 10 + HEAD_LEN)
    const altStart = fullCore.indexOf(altHead)
    if (altStart !== -1) startCoreIdx = Math.max(0, altStart - 10)
  }

  if (startCoreIdx === -1) return md.render(fullText)

  // ✅ 关键修复 1：在 startCoreIdx 之后的合理窗口内找尾部，防止跨段贪婪匹配
  const searchEndCoreIdx = Math.min(fullCore.length, startCoreIdx + chunkCore.length + 150)
  const searchArea = fullCore.substring(startCoreIdx, searchEndCoreIdx)
  const localTailIdx = searchArea.lastIndexOf(tailStr)

  let endCoreIdx
  if (localTailIdx !== -1) {
    endCoreIdx = startCoreIdx + localTailIdx + TAIL_LEN
  } else {
    // 尾部实在找不到（被表格符号打散），按核心字数量推算
    endCoreIdx = Math.min(fullCore.length, startCoreIdx + chunkCore.length)
  }

  // ✅ 关键修复 2：endCoreIdx 越界保护
  const safeEnd = Math.min(endCoreIdx, fullMap.length) - 1
  if (safeEnd < 0 || startCoreIdx >= fullMap.length) return md.render(fullText)

  const realStart = fullMap[startCoreIdx]
  const realEnd = fullMap[safeEnd] + 1

  // ✅ 关键修复 3：用 \n\n（段落边界）扩展，而不是 \n（行边界）
  // \n 在 Markdown 表格/标题中间隔极远，会把大片无关内容吞进高亮区
  let expandStart = fullText.lastIndexOf('\n\n', realStart)
  expandStart = expandStart === -1 ? 0 : expandStart + 2

  let expandEnd = fullText.indexOf('\n\n', realEnd)
  expandEnd = expandEnd === -1 ? fullText.length : expandEnd

  // ✅ 关键修复 4：扩展范围过大时（>原 chunk 字符数 * 3）直接回退到精确位置，不扩展
  if (expandEnd - expandStart > pureChunk.length * 3) {
    expandStart = realStart
    expandEnd = realEnd
  }

  const before = fullText.substring(0, expandStart)
  const highlight = fullText.substring(expandStart, expandEnd)
  const after = fullText.substring(expandEnd)

  return md.render(`${before}\n\n<mark class="chunk-highlight">\n\n${highlight}\n\n</mark>\n\n${after}`)
}

const handleCitationClick = (event) => {
  const target = event.target.closest('.citation-btn')
  if (!target) return

  const origIndex = parseInt(target.getAttribute('data-orig-index'))
  const msgRow = target.closest('.msg-row')
  if (!msgRow) return

  const msgIndex = parseInt(msgRow.getAttribute('data-msg-index'))
  const msg = history.value[msgIndex]

  if (msg && msg.evidences && msg.evidences.length > 0) {
    const ev = msg.evidences.find(e => e.index === origIndex) || msg.evidences[origIndex - 1]
    if (ev) openCitationDetail(ev)
  }
}

const openCitationDetail = (ev) => {
  if(!ev.index) ev.index = evidences.value.indexOf(ev) + 1
  currentCitation.value = ev
  rightPanelMode.value = 'detail' 
}

const openPdf = (ev) => { /* ... */ }

const toggleSelection = (id) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx > -1) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

onMounted(fetchSources)
</script>

<style scoped>
/* ========== 全局与面板 ========== */
.app-layout { position: fixed; top: 0; left: 0; right: 0; bottom: 0; display: flex; background-color: #fcfcfd; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 12px; color: #2c3e50; overflow: hidden; }
.panel { display: flex; flex-direction: column; background: #fff; height: 100%; }
.center-panel { flex: 1; min-width: 300px; background: #fff; }
.panel-header { height: 42px; border-bottom: 1px solid #ebEEF5; display: flex; align-items: center; padding: 0 10px; justify-content: space-between; flex-shrink: 0; background: #fdfdfd; }
.header-title { font-weight: 600; font-size: 13px; }
.panel-body { flex: 1; overflow-y: auto; }
.bg-gray { background-color: #fafafa; }
.resizer { width: 1px; background: #e0e0e0; cursor: col-resize; z-index: 10; flex-shrink: 0; position: relative; }
.resizer::after { content: ''; position: absolute; left: -3px; right: -3px; top: 0; bottom: 0; z-index: 1; }
.resizer:hover { background: #409eff; width: 2px; }

/* ========== 左侧样式 ========== */
.group-label { padding: 10px 10px 4px; font-size: 11px; color: #909399; font-weight: 600; }
.source-item { display: flex; align-items: center; padding: 0 10px; cursor: pointer; height: 28px; font-size: 12px; }
.source-item:hover { background: #f2f6fc; }
.source-item.active { background: #ecf5ff; color: #409eff; }
.source-item.is-processing { opacity: 0.6; cursor: wait; background: transparent; }
.file-icon { margin-right: 6px; color: #909399; font-size: 13px; }
.file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.del-icon { display: none; color: #f56c6c; padding: 4px; font-size: 12px; }
.source-item:hover .del-icon { display: block; }
.mini-checkbox { margin-right: 4px; transform: scale(0.8); }
.panel-footer { height: 32px; border-top: 1px solid #ebEEF5; display: flex; align-items: center; justify-content: space-between; padding: 0 10px; font-size: 11px; color: #909399; background: #fafafa; }
@keyframes rotating { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.custom-spin { animation: rotating 2s linear infinite; color: #409eff; }

/* ========== 中间聊天框 ========== */
.chat-header { height: 42px; border-bottom: 1px solid #ebEEF5; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 13px; background: #fff; }
.chat-viewport { flex: 1; overflow-y: auto; padding: 15px; }
.msg-row { display: flex; margin-bottom: 16px; gap: 8px; }
.msg-row.user { flex-direction: row-reverse; }
.avatar { width: 24px; height: 24px; background: #f0f2f5; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; color: #606266; flex-shrink: 0; }
.msg-row.user .avatar { background: #409eff; color: #fff; }
.bubble { max-width: 100%; padding: 6px 10px; border-radius: 6px; line-height: 1.5; font-size: 12px; }
.msg-row.user .bubble { background: #ecf5ff; color: #409eff; }

:deep(.citation-btn) { color: #0b57d0; cursor: pointer; font-size: 0.85em; font-weight: 600; margin: 0 2px; padding: 1px 4px; border-radius: 4px; background-color: #e8f0fe; transition: all 0.2s ease; user-select: none; }
:deep(.citation-btn):hover { background-color: #0b57d0; color: #fff; }

.input-area { padding: 0 15% 30px; background: linear-gradient(to bottom, rgba(255,255,255,0), #fff 40%); z-index: 10; display: flex; justify-content: center; }
.gemini-input-wrapper { width: 100%; max-width: 800px; position: relative; display: flex; align-items: flex-end; background-color: #f0f4f9; border-radius: 28px; padding: 12px 16px; border: 1px solid transparent; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }
.gemini-input-wrapper:focus-within { background-color: #fff; border-color: #d3e3fd; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); transform: translateY(-1px); }
.gemini-textarea { flex: 1; margin-right: 8px; }
.gemini-textarea :deep(.el-textarea__inner) { background: transparent !important; box-shadow: none !important; border: none !important; padding: 4px 0; font-size: 15px; line-height: 24px; color: #1f1f1f; resize: none; min-height: 32px !important; height: 32px; }
.gemini-textarea :deep(.el-textarea__inner)::-webkit-scrollbar { width: 0; }
.send-btn-box { flex-shrink: 0; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; }
.gemini-send-btn { width: 32px; height: 32px; font-size: 16px; transition: all 0.2s; background-color: transparent; color: #1f1f1f; border: none; }
.gemini-input-wrapper:focus-within .gemini-send-btn, .gemini-send-btn:not(.is-disabled) { background-color: #0b57d0; color: #fff; }
.gemini-send-btn:hover { transform: scale(1.05); box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
.gemini-send-btn.is-disabled { background-color: transparent; color: #ccc; }

/* ========== 右侧列表与卡片 ========== */
.mini-tag { transform: scale(0.9); }
.evidence-card { background: #fff; border: 1px solid #ebEEF5; border-radius: 4px; padding: 8px; margin: 8px; transition: all 0.1s; cursor: pointer; }
.evidence-card:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,0.04); border-color: #c6e2ff; }
.ev-meta { display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 4px; color: #909399; }
.score { color: #67c23a; font-family: monospace; }
.ev-text { font-size: 11px; line-height: 1.4; color: #606266; margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.ev-source { display: flex; align-items: center; gap: 4px; font-size: 10px; color: #909399; padding-top: 4px; border-top: 1px solid #f2f6fc; }
.trunc-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px; }
.page-tag { margin-left: auto; background: #fdf6ec; color: #e6a23c; padding: 1px 3px; border-radius: 2px; }

/* ========== 右侧详情头部 ========== */
.notebooklm-header { padding: 16px 20px 10px; background: #fff; display: flex; flex-direction: column; gap: 4px; border-bottom: 1px solid transparent; }
.source-label { font-size: 11px; color: #5f6368; font-weight: 500; }
.header-main-row { display: flex; justify-content: space-between; align-items: center; }
.doc-title { font-size: 18px; font-weight: 500; color: #1f1f1f; margin: 0; padding: 0; line-height: 1.2; }
.close-btn { cursor: pointer; width: 28px; height: 28px; border-radius: 50%; background: #f1f3f4; display: flex; align-items: center; justify-content: center; color: #5f6368; }
.close-btn:hover { background: #e8eaed; color: #202124; }
.citation-meta-tags { display: flex; gap: 8px; margin-top: 8px; }

/* ========== 调试面板样式 ========== */
.debug-panel { margin-bottom: 16px; padding: 12px; background-color: #1e1e1e; border-radius: 6px; border: 1px solid #333; }
.debug-title { font-size: 12px; font-weight: bold; color: #4af626; margin-bottom: 6px; }
.debug-code { font-family: Consolas, Monaco, monospace; font-size: 12px; color: #d4d4d4; white-space: pre-wrap; word-wrap: break-word; background: #2d2d2d; padding: 8px; border-radius: 4px; margin: 0; }

/* ========== 右侧 Markdown 详情与高亮 ========== */
.citation-detail-body { flex: 1; padding: 16px 20px; background: #fff; border-top: 1px solid #f1f3f4;}
.custom-md { font-size: 13px; line-height: 1.6; color: #3c4043; }
.custom-md :deep(h1), .custom-md :deep(h2), .custom-md :deep(h3) { font-size: 14px; font-weight: 600; margin-top: 0; margin-bottom: 8px;}
.custom-md :deep(p) { margin-bottom: 12px; }
.custom-md :deep(table) { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
.custom-md :deep(th), .custom-md :deep(td) { border: 1px solid #dadce0; padding: 6px; }

/* 用于匹配文本的柔和高亮块样式 */
:deep(mark.chunk-highlight) {
  background-color: rgba(255, 235, 140, 0.4);
  border-left: 4px solid #fadb14;
  padding: 4px 8px;
  border-radius: 0 4px 4px 0;
  display: block; 
  margin: 8px 0;
  color: inherit;
  transition: all 0.3s;
}
:deep(mark.chunk-highlight:hover) {
  background-color: rgba(255, 235, 140, 0.7);
}

/* ========== 右侧 PDF ========== */
.notebooklm-body { flex: 1; overflow: hidden; background: #fff; display: flex; flex-direction: column; }
.clean-pdf-viewer { background: #fff !important; }
:deep(.pdf-app-container) { background-color: #fff !important; }
:deep(#viewerContainer) { background-color: #fff !important; padding: 0 !important; }
:deep(.page) { margin: 0 auto 20px !important; box-shadow: none !important; border: none !important; border-bottom: 1px solid #f1f3f4 !important; }
:deep(#viewerContainer::-webkit-scrollbar) { width: 8px; }
:deep(#viewerContainer::-webkit-scrollbar-thumb) { background-color: #dadce0; border-radius: 4px; }
:deep(.el-checkbox__label) { display: none; }
:deep(.markdown-body p) { margin-bottom: 6px; }
</style>