<template>
  <div class="chat-layout">
    <!-- 移动端侧边栏遮罩 -->
    <div class="sidebar-backdrop" v-if="isSidebarOpen" @click="toggleSidebar"></div>

    <!-- 左侧会话列表侧边栏 -->
    <aside :class="['chat-sidebar', { 'is-open': isSidebarOpen }]">
      <div class="sidebar-header">
        <button class="new-chat-btn" @click="createNewSession">
          <span class="plus-icon">+</span> 新建对话
        </button>
      </div>
      <div class="session-list">
        <div 
          v-for="session in sessions" 
          :key="session.id"
          :class="['session-item', { active: session.id === currentSessionId }]"
          @click="switchSession(session.id)"
        >
          <span class="session-icon">💬</span>
          <span class="session-title">{{ session.title }}</span>
          <button class="delete-session-btn" @click.stop="deleteSession(session.id)" title="删除对话">✕</button>
        </div>
      </div>
    </aside>

    <!-- 右侧主聊天区域 -->
    <main class="chat-main">
      <header class="chat-header">
        <div class="header-left">
          <button class="menu-btn" @click="toggleSidebar">☰</button>
          <div class="nav-links">
            <router-link to="/chat" class="nav-link">聊天</router-link>
            <router-link to="/kb" class="nav-link">知识库</router-link>
          </div>
        </div>
        <button @click="handleLogout" class="logout-btn">退出</button>
      </header>
      
      <div class="message-list" ref="messageListRef">
      <div 
        v-for="(msg, index) in messages" 
        :key="index"
        :class="['message-wrapper', msg.role === 'user' ? 'is-user' : 'is-ai']"
        v-show="!(msg.role === 'ai' && msg.content === '' && loading)"
      >
        <div class="avatar" v-if="msg.role === 'ai'">🤖</div>
        <div class="message-bubble">
          <div v-if="msg.role === 'ai'" class="message-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
          <div v-else class="message-content">{{ msg.content }}</div>
          <!-- 知识库引用来源 UI -->
          <div v-if="msg.citations && msg.citations.length > 0" class="citations-container">
            <div class="citation-divider"></div>
            <div class="citation-title">来源：</div>
            <div class="citation-tags">
              <span class="citation-tag" v-for="(citation, cIndex) in msg.citations" :key="cIndex">
                [{{ cIndex + 1 }}] {{ citation }}
              </span>
            </div>
          </div>
        </div>
        <div class="avatar" v-if="msg.role === 'user'">👤</div>
      </div>
      
      <!-- 加载中骨架屏 -->
      <div class="message-wrapper is-ai" v-if="loading">
        <div class="avatar">🤖</div>
        <div class="message-bubble loading-bubble">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="chat-input-area">
      <div class="input-wrapper">
        <div class="file-pills-container" v-if="selectedFiles.length > 0">
          <div class="file-pill" v-for="(file, index) in selectedFiles" :key="index">
            <span class="file-icon">📄</span>
            <span class="file-name">{{ file.name }}</span>
            <button class="remove-file-btn" @click="removeFile(index)">✕</button>
          </div>
        </div>
        
        <div class="textarea-container">
          <label class="upload-btn">
            <input type="file" @change="handleFileSelect" accept=".txt,.md" hidden multiple />
            📎
          </label>
          <textarea 
            class="monica-chat-input"
            v-model="inputMsg" 
            @keydown.enter.prevent="sendMessage"
            @input="autoResize"
            placeholder="问我任何问题..." 
            :disabled="loading"
            ref="textareaRef"
          ></textarea>
        </div>
      </div>
      <button class="send-btn" @click="sendMessage" :disabled="loading || (!inputMsg.trim() && selectedFiles.length === 0)">
        {{ loading ? '发送中...' : '发送' }}
      </button>
    </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import request from '../api/request';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css'; // 使用 GitHub 浅色主题

// 配置 marked 使用 highlight.js
marked.setOptions({
  highlight: function (code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  },
  breaks: true, // 允许回车换行
});

const renderMarkdown = (text: string) => {
  if (!text) return '';
  // 简单处理引用块的特殊渲染需求，可选
  return marked.parse(text);
};

const router = useRouter();
const inputMsg = ref('');
const loading = ref(false);
const messageListRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const selectedFiles = ref<File[]>([]);

// 扩展 Message 类型，增加 citations
interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  citations?: string[];
}

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
}

const sessions = ref<ChatSession[]>([]);
const currentSessionId = ref<string>('');
const isSidebarOpen = ref(false);

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const currentSession = computed(() => sessions.value.find(s => s.id === currentSessionId.value));
const messages = computed(() => currentSession.value?.messages || []);

const createNewSession = async () => {
  try {
    const res: any = await request.post('/assistant/sessions', { sessionTitle: '新对话' });
    if (res.code === 200 && res.data) {
      const newSession: ChatSession = {
        id: res.data.id.toString(),
        title: res.data.sessionTitle,
        messages: [{ role: 'ai', content: '您好！我是您的售后助手，有什么可以帮助您？' }],
        updatedAt: new Date(res.data.lastActiveTime).getTime()
      };
      sessions.value.unshift(newSession);
      currentSessionId.value = newSession.id;
    }
  } catch (e) {
    console.error('Failed to create session', e);
  }
};

const loadMessages = async (id: string) => {
  try {
    const res: any = await request.get(`/assistant/sessions/${id}/messages`);
    if (res.code === 200 && res.data) {
      const session = sessions.value.find(s => s.id === id);
      if (session) {
        session.messages = res.data.map((m: any) => ({
          role: m.role,
          content: m.content
        }));
        // 若没有消息，则添加默认问候语
        if (session.messages.length === 0) {
          session.messages.push({ role: 'ai', content: '您好！我是您的售后助手，有什么可以帮助您？' }); 
        }
        await scrollToBottom();
      }
    }
  } catch (e) {
    console.error('Failed to load messages', e);
  }
};

const switchSession = async (id: string) => {
  if (loading.value) return; // 请求中不允许切换会话
  currentSessionId.value = id;
  isSidebarOpen.value = false; // 移动端切换后自动收起侧边栏
  await loadMessages(id);
};

const deleteSession = async (id: string) => {
  if (loading.value) return;
  try {
    const res: any = await request.delete(`/assistant/sessions/${id}`);
    if (res.code === 200) {
      const index = sessions.value.findIndex(s => s.id === id);
      if (index !== -1) {
        sessions.value.splice(index, 1);
        // 如果全部删除完毕，自动创建一个新会话
        if (sessions.value.length === 0) {
          await createNewSession();
        } else if (currentSessionId.value === id) {
          // 如果删除的是当前会话，切换到第一个会话
          currentSessionId.value = sessions.value[0].id;
          await loadMessages(currentSessionId.value);
        }
      }
    }
  } catch (e) {
    console.error('Failed to delete session', e);
  }
};

const fetchSessions = async () => {
  try {
    const res: any = await request.get('/assistant/sessions');
    if (res.code === 200 && res.data) {
      sessions.value = res.data.map((s: any) => ({
        id: s.id.toString(),
        title: s.sessionTitle,
        updatedAt: new Date(s.lastActiveTime).getTime(),
        messages: [] // messages will be loaded lazily
      }));
      
      if (sessions.value.length === 0) {
        await createNewSession();
      } else {
        currentSessionId.value = sessions.value[0].id;
        await loadMessages(currentSessionId.value);
      }
    }
  } catch (e) {
    console.error('Failed to fetch sessions', e);
  }
};

onMounted(() => {
  fetchSessions();
});

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const filesArray = Array.from(target.files);
    // 可选：检查文件类型，虽然 input accept 已限制
    const validFiles = filesArray.filter(file => file.name.endsWith('.txt') || file.name.endsWith('.md'));
    selectedFiles.value.push(...validFiles);
    target.value = ''; // 重置 input，允许重复选择同一个文件
  }
};

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1);
};

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = '48px';
    const scrollHeight = textareaRef.value.scrollHeight;
    textareaRef.value.style.height = `${Math.min(Math.max(scrollHeight, 48), 144)}px`;
    if (scrollHeight > 144) {
      textareaRef.value.style.overflowY = 'auto';
    } else {
      textareaRef.value.style.overflowY = 'hidden';
    }
  }
};

const scrollToBottom = async () => {
  await nextTick();
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
  }
};

const sendMessage = async () => {
  if ((!inputMsg.value.trim() && selectedFiles.value.length === 0) || loading.value || !currentSession.value) return;
  
  const userText = inputMsg.value;
  // 暂时在这里将文件信息附在文本中，后续您对接 RAG 接口时可以调整传参结构
  const fileNames = selectedFiles.value.map(f => f.name).join(', ');
  const displayMsg = userText + (fileNames ? `\n[已附带文件: ${fileNames}]` : '');
  
  // 上传文件到知识库以便 RAG 检索
  if (selectedFiles.value.length > 0) {
    for (const file of selectedFiles.value) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        await request.post('/kb/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      } catch (err) {
        console.error('Failed to upload file to KB', err);
      }
    }
  }
  
  // 如果是新对话的第一条用户消息，用截断的用户输入更新会话标题
  if (currentSession.value.messages.length === 1 && userText) {
    currentSession.value.title = userText.length > 12 ? userText.slice(0, 12) + '...' : userText;
  }
  
  currentSession.value.messages.push({ role: 'user', content: displayMsg });
  currentSession.value.updatedAt = Date.now();
  
  inputMsg.value = '';
  selectedFiles.value = []; // 发送后清空附件
  loading.value = true;
  if (textareaRef.value) {
    textareaRef.value.style.height = '48px';
    textareaRef.value.style.overflowY = 'hidden';
  }
  await scrollToBottom();

  // 先在列表中占位一个空的 AI 消息，用于接收流式打字数据
  const aiMsg: ChatMessage = { 
    role: 'ai', 
    content: '',
    citations: fileNames ? fileNames.split(', ') : undefined
  };
  currentSession.value.messages.push(aiMsg);
  
  // Vue 3 的 reactivity：向响应式数组 push 原生对象后，数组里的元素会变成 Proxy
  // 必须通过数组索引获取到这个 Proxy 对象并修改它的属性，才能触发 Vue 的 DOM 更新！
  // 之前直接修改原生的 aiMsg 变量是无法触发前端显示的。
  const reactiveAiMsg = currentSession.value.messages[currentSession.value.messages.length - 1];
  
  try {
    // 获取当前用户的 token
    const token = localStorage.getItem('satoken');
    
    // 使用 fetch API 接收 SSE 数据流
    const response = await fetch('/api/assistant/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'satoken': token || ''
      },
      body: JSON.stringify({
        question: displayMsg,
        sessionId: currentSessionId.value
      })
    });

    if (!response.body) throw new Error('您的浏览器不支持 ReadableStream');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let done = false;
    let accumulatedContent = '';
    let streamBuffer = '';

    // 持续监听和拼接打字机流式数据
    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        streamBuffer += chunk;
        
        // 按照 SSE 标准，每个事件以两个换行符 \n\n 分隔
        const events = streamBuffer.split('\n\n');
        // 将最后一个可能不完整的事件放回 buffer 中留待下次拼接
        streamBuffer = events.pop() || '';
        
        for (const event of events) {
          // 只关心以 data: 开头的内容（SSE 可能会有 event:, id: 等，但我们目前只发送了 data:）
          const dataMatch = event.match(/^data:\s*(.*)/m);
          if (dataMatch && dataMatch[1]) {
            try {
              // 这里的 dataMatch[1] 是包含在 data: 后面直到行尾的字符串，由于后端序列化为 JSON 且转义了换行符，它应该是完整的单行 JSON
              const dataStr = dataMatch[1].trim();
              if (dataStr) {
                const data = JSON.parse(dataStr);
                // 收到第一笔真实数据时，关闭 loading 骨架屏，避免出现两个回复框
                if (loading.value) {
                  loading.value = false;
                }
                accumulatedContent += data.content;
                reactiveAiMsg.content = accumulatedContent;
              }
            } catch (e) {
              console.error('SSE JSON 解析错误:', e, event);
            }
          }
        }
        
        await scrollToBottom();
      }
    }
  } catch (error) {
    console.error('发送失败:', error);
    const message = error instanceof Error ? error.message : '服务暂时不可用，请稍后重试。';
    reactiveAiMsg.content += `\n[Error: ${message}]`;
  } finally {
    if (currentSession.value) {
      currentSession.value.updatedAt = Date.now();
    }
    loading.value = false;
    await scrollToBottom();
    await fetchSessions(); // 更新侧边栏列表（如果是新对话需要刷新标题）
  }
};

const handleLogout = () => {
  localStorage.removeItem('satoken');
  router.push('/login');
};
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  max-width: 100%;
  margin: 0;
  padding: 0;
  background-color: #f0f4f8;
  overflow: hidden;
}

/* Sidebar Styles */
.chat-sidebar {
  width: 260px;
  background-color: #f9f9f9;
  border-right: 1px solid #eaeaea;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #eaeaea;
}
.new-chat-btn {
  width: 100%;
  padding: 10px;
  background-color: #ffffff;
  border: 1px solid #eaeaea;
  border-radius: 8px;
  color: #333;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background-color 0.2s, border-color 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.new-chat-btn:hover {
  background-color: #f0f0f0;
  border-color: #d0d0d0;
}
.plus-icon {
  font-size: 18px;
  font-weight: normal;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
  color: #555;
}
.session-item:hover {
  background-color: #eaeaea;
}
.session-item.active {
  background-color: #e6f6ef;
  color: #42b983;
  font-weight: bold;
}
.session-icon {
  margin-right: 10px;
  font-size: 16px;
}
.session-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
}
.delete-session-btn {
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  opacity: 0;
  padding: 4px;
  transition: opacity 0.2s, color 0.2s;
}
.session-item:hover .delete-session-btn {
  opacity: 1;
}
.delete-session-btn:hover {
  color: #ff4d4f;
}

/* Main Chat Area Styles */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  min-width: 0; /* 关键：防止 flex 子项内容撑破父容器产生水平滚动条 */
  width: 100%;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background-color: #ffffff;
  border-bottom: 1px solid #eaeaea;
  z-index: 10;
}
.header-left {
  display: flex;
  align-items: center;
}
.menu-btn {
  display: none;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  margin-right: 15px;
  color: #333;
}
.sidebar-backdrop {
  display: none;
}
.nav-links {
  display: flex;
  gap: 15px;
}
.nav-link {
  text-decoration: none;
  color: #333;
  font-weight: bold;
  padding: 5px 10px;
  border-radius: 4px;
}
.nav-link.router-link-active {
  background-color: #42b983;
  color: white;
}
.logout-btn {
  padding: 5px 10px;
  background-color: #ff4d4f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.message-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  max-width: 85%;
}
.message-wrapper.is-user {
  align-self: flex-end;
}
.message-wrapper.is-ai {
  align-self: flex-start;
}
.avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 18px;
  flex-shrink: 0;
}
.is-user .avatar {
  background-color: #e6f6ef;
}
.is-ai .avatar {
  background-color: #ffffff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  border: 1px solid #eaeaea;
}
.message-bubble {
  padding: 12px 16px;
  font-size: 15px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.is-user .message-bubble {
  background-color: #42b983;
  color: white;
  border-radius: 16px 16px 4px 16px;
  box-shadow: 0 2px 8px rgba(66, 185, 131, 0.2);
}
.is-ai .message-bubble {
  background-color: #ffffff;
  color: #333338;
  border-radius: 16px 16px 16px 4px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  border: 1px solid #eaeaea;
  min-width: 60px; /* 保证骨架屏不会太窄 */
}

/* Typing Indicator (骨架屏动画) */
.loading-bubble {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 44px;
}
.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  background-color: #a0a0a0;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out both;
}
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
@keyframes typing {
  0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* Citations UI */
.citations-container {
  margin-top: 12px;
  font-size: 12px;
}
.citation-divider {
  height: 1px;
  background-color: #eaeaea;
  margin-bottom: 8px;
}
.citation-title {
  color: #999;
  margin-bottom: 6px;
}
.citation-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.citation-tag {
  background-color: #f5f5f5;
  color: #666;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #eaeaea;
}

/* Markdown Styles */
:deep(.markdown-body) {
  font-family: inherit;
}
:deep(.markdown-body p) {
  margin-top: 0;
  margin-bottom: 8px;
}
:deep(.markdown-body p:last-child) {
  margin-bottom: 0;
}
:deep(.markdown-body pre) {
  background-color: #f6f8fa;
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  margin: 12px 0;
}
:deep(.markdown-body code) {
  font-family: Consolas, Monaco, 'Andale Mono', 'Ubuntu Mono', monospace;
  font-size: 13px;
}
:deep(.markdown-body p code) {
  background-color: rgba(0,0,0,0.05);
  padding: 2px 4px;
  border-radius: 4px;
  color: #eb5757;
}
:deep(.markdown-body table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}
:deep(.markdown-body th), :deep(.markdown-body td) {
  border: 1px solid #dfe2e5;
  padding: 6px 13px;
}
:deep(.markdown-body th) {
  background-color: #f6f8fa;
}

.chat-input-area {
  display: flex;
  padding: 20px;
  border-top: 1px solid #eaeaea;
  gap: 12px;
  align-items: flex-end;
  background-color: #ffffff;
  box-sizing: border-box; /* 确保 padding 不会撑大宽度 */
}
.input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  background-color: #ffffff;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 6px rgba(0,0,0,0.02);
}
.input-wrapper:focus-within {
  border-color: #42b983;
  box-shadow: 0 2px 8px rgba(66, 185, 131, 0.1);
}
.file-pills-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 12px 0 12px;
}
.file-pill {
  display: flex;
  align-items: center;
  background-color: #f5f5f5;
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 13px;
  color: #333;
}
.file-icon {
  margin-right: 6px;
  font-size: 14px;
}
.file-name {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.remove-file-btn {
  background: none;
  border: none;
  margin-left: 6px;
  color: #999;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
}
.remove-file-btn:hover {
  color: #ff4d4f;
}
.textarea-container {
  display: flex;
  align-items: flex-start;
  padding: 8px 12px;
  gap: 8px;
}
.upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  color: #666;
  font-size: 18px;
  margin-top: 2px;
  transition: background-color 0.2s;
}
.upload-btn:hover {
  background-color: #f0f0f0;
  color: #42b983;
}
.monica-chat-input {
  display: inline-block;
  width: 100%;
  flex: 1;
  height: 32px;
  min-height: 32px;
  max-height: 120px;
  box-sizing: border-box;
  border: none;
  font-family: inherit;
  font-size: 15px;
  line-height: 24px;
  white-space: pre-wrap;
  color: #333338;
  cursor: text;
  padding: 4px 0;
  overflow-y: hidden;
  resize: none;
  background: transparent;
}
.monica-chat-input:hover, .monica-chat-input:focus {
  outline: none;
}
.monica-chat-input:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.send-btn {
  padding: 0 20px;
  height: 48px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: bold;
  transition: background-color 0.2s, transform 0.1s;
}
.send-btn:hover:not(:disabled) {
  background-color: #3aa876;
}
.send-btn:active:not(:disabled) {
  transform: scale(0.98);
}
.send-btn:disabled {
  background-color: #a0d8b8;
  cursor: not-allowed;
}

/* 响应式媒体查询 (Mobile) */
@media (max-width: 768px) {
  .menu-btn {
    display: block;
  }
  .chat-sidebar {
    position: fixed;
    left: -260px;
    top: 0;
    bottom: 0;
    z-index: 100;
    transition: left 0.3s ease;
    box-shadow: 2px 0 8px rgba(0,0,0,0.1);
  }
  .chat-sidebar.is-open {
    left: 0;
  }
  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background-color: rgba(0,0,0,0.4);
    z-index: 90;
  }
  .message-wrapper {
    max-width: 95%; /* 移动端气泡更宽 */
  }
  .chat-input-area {
    padding: 10px;
  }
  .send-btn {
    padding: 0 12px; /* 按钮缩小点 */
  }
  .monica-chat-input {
    font-size: 14px;
  }
}
</style>
