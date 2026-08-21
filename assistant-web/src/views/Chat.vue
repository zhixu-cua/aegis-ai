<template>
  <div class="chat-container">
    <header class="chat-header">
      <h2>聊天</h2>
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
          <textarea 
            class="chat-input"
            v-model="inputMsg" 
            @keydown.enter.prevent="sendMessage"
            @input="autoResize"
            placeholder="输入您的问题..." 
            :disabled="loading"
            ref="textareaRef"
          ></textarea>
          
          <div class="input-actions">
            <!-- <label class="action-btn upload-btn" title="支持格式: .txt, .md, .pdf, .docx, .doc, .xlsx, .xls, .csv, .png, .jpg, .jpeg, .html, .htm">
              <input type="file" @change="handleFileSelect" accept=".txt,.md,.pdf,.docx,.doc,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.html,.htm" hidden multiple />
              📎 附件
            </label> -->
            <button class="action-btn send-btn" style="margin-left: auto;" @click="sendMessage" :disabled="loading || (!inputMsg.trim() && selectedFiles.length === 0)">
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue';
import { useChatStore, type ChatMessage } from '@/stores/chat';
import request from '../api/request';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css'; // 使用 GitHub 浅色主题

// 配置 marked 使用 highlight.js
(marked as any).setOptions({
  highlight: function (code: string, lang: string) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  },
  breaks: true, // 允许回车换行
});

const renderMarkdown = (text: string) => {
  if (!text) return '';
  return marked.parse(text);
};

const chatStore = useChatStore();
const inputMsg = ref('');
const loading = ref(false);
const messageListRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const selectedFiles = ref<File[]>([]);

const currentSession = computed(() => chatStore.currentSession);
const messages = computed(() => currentSession.value?.messages || []);

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const filesArray = Array.from(target.files);
    const validExtensions = ['.txt', '.md', '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.png', '.jpg', '.jpeg', '.html', '.htm'];
    const validFiles = filesArray.filter(file => {
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      return validExtensions.includes(ext);
    });
    selectedFiles.value.push(...validFiles);
    target.value = ''; 
  }
};

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1);
};

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = '24px';
    const scrollHeight = textareaRef.value.scrollHeight;
    textareaRef.value.style.height = `${Math.min(Math.max(scrollHeight, 24), 120)}px`;
    if (scrollHeight > 120) {
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
  const fileNames = selectedFiles.value.map(f => f.name).join(', ');
  const displayMsg = userText + (fileNames ? `\n[已附带文件: ${fileNames}]` : '');
  
  if (selectedFiles.value.length > 0) {
    for (const file of selectedFiles.value) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res: any = await request.post('/kb/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        if (res.code !== 200) {
           console.error(`上传文件 ${file.name} 失败:`, res.message);
        }
      } catch (err) {
        console.error('Failed to upload file to KB', err);
      }
    }
  }
  
  if (chatStore.currentSessionId === 'temp_new_session') {
    const realSessionId = await chatStore.createRealSession(userText.length > 12 ? userText.slice(0, 12) + '...' : userText || '新对话');
    if (!realSessionId) {
      alert('创建对话失败，请稍后重试');
      return;
    }
  } else if (currentSession.value.messages.length === 1 && userText) {
    currentSession.value.title = userText.length > 12 ? userText.slice(0, 12) + '...' : userText;
  }
  
  currentSession.value.messages.push({ role: 'user', content: displayMsg });
  currentSession.value.updatedAt = Date.now();
  
  inputMsg.value = '';
  selectedFiles.value = []; 
  loading.value = true;
  if (textareaRef.value) {
    textareaRef.value.style.height = '24px';
    textareaRef.value.style.overflowY = 'hidden';
  }
  await scrollToBottom();

  const aiMsg: ChatMessage = { 
    role: 'ai', 
    content: '',
    citations: fileNames ? fileNames.split(', ') : undefined
  };
  currentSession.value.messages.push(aiMsg);
  
  const reactiveAiMsg = currentSession.value.messages[currentSession.value.messages.length - 1];
  
  try {
    const token = localStorage.getItem('satoken');
    const response = await fetch('/api/assistant/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'satoken': token || ''
      },
      body: JSON.stringify({
        question: displayMsg,
        sessionId: chatStore.currentSessionId
      })
    });

    if (!response.body) throw new Error('您的浏览器不支持 ReadableStream');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let done = false;
    let accumulatedContent = '';
    let streamBuffer = '';

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        streamBuffer += chunk;
        
        const events = streamBuffer.split('\n\n');
        streamBuffer = events.pop() || '';
        
        for (const event of events) {
          const dataMatch = event.match(/^data:\s*(.*)/m);
          if (dataMatch && dataMatch[1]) {
            try {
              const dataStr = dataMatch[1].trim();
              if (dataStr) {
                const data = JSON.parse(dataStr);
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
  }
};
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background-color: #f5f7fa;
}

.chat-header {
  padding: 16px 24px;
  background-color: #ffffff;
  border-bottom: 1px solid #eef0f4;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  z-index: 10;
}

.chat-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 10%;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message-wrapper {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  max-width: 85%;
}

.message-wrapper.is-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-wrapper.is-ai {
  align-self: flex-start;
}

.avatar {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 20px;
  flex-shrink: 0;
  background-color: #ffffff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.is-user .avatar {
  background-color: #eef1fe;
}

.message-bubble {
  padding: 14px 20px;
  font-size: 15px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.is-user .message-bubble {
  background-color: #4f6ef7;
  color: #ffffff;
  border-radius: 16px 4px 16px 16px;
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.2);
}

.is-ai .message-bubble {
  background-color: #ffffff;
  color: #1d2129;
  border-radius: 4px 16px 16px 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.04);
  border: 1px solid #eef0f4;
  min-width: 60px;
}

/* Typing Indicator */
.loading-bubble {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 24px;
}
.typing-indicator {
  display: flex;
  gap: 6px;
  align-items: center;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  background-color: #86909c;
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
  background-color: #eef0f4;
  margin-bottom: 8px;
}
.citation-title {
  color: #86909c;
  margin-bottom: 6px;
}
.citation-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.citation-tag {
  background-color: #f2f3f5;
  color: #4e5969;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #eef0f4;
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
  background-color: #f2f3f5;
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

/* Input Area */
.chat-input-area {
  padding: 0 10% 32px 10%;
  background-color: transparent;
}

.input-wrapper {
  background-color: #ffffff;
  border: 1px solid #eef0f4;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.04);
  transition: all 0.2s ease;
  overflow: hidden;
}

.input-wrapper:focus-within {
  border-color: #4f6ef7;
  box-shadow: 0 4px 16px rgba(79, 110, 247, 0.1);
}

.textarea-container {
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.chat-input {
  width: 100%;
  height: 24px;
  min-height: 24px;
  max-height: 120px;
  border: none;
  font-family: inherit;
  font-size: 15px;
  line-height: 24px;
  color: #1d2129;
  resize: none;
  background: transparent;
  outline: none;
}

.chat-input::placeholder {
  color: #86909c;
}

.chat-input:disabled {
  cursor: not-allowed;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.upload-btn {
  background-color: transparent;
  color: #4e5969;
}

.upload-btn:hover {
  background-color: #f2f3f5;
  color: #1d2129;
}

.send-btn {
  background-color: #4f6ef7;
  color: #ffffff;
}

.send-btn:hover:not(:disabled) {
  background-color: #3a5cd8;
}

.send-btn:disabled {
  background-color: #b2c1ff;
  cursor: not-allowed;
}

.file-pills-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px 0 16px;
}

.file-pill {
  display: flex;
  align-items: center;
  background-color: #f2f3f5;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 13px;
  color: #4e5969;
}

.file-icon {
  margin-right: 6px;
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
  color: #86909c;
  cursor: pointer;
  padding: 0 2px;
}

.remove-file-btn:hover {
  color: #e53935;
}
</style>
