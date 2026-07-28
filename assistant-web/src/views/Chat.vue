<template>
  <div class="chat-container">
    <header class="chat-header">
      <div class="nav-links">
        <router-link to="/chat" class="nav-link">Chat</router-link>
        <router-link to="/kb" class="nav-link">Knowledge Base</router-link>
      </div>
      <button @click="handleLogout" class="logout-btn">Logout</button>
    </header>
    
    <div class="message-list" ref="messageListRef">
      <div 
        v-for="(msg, index) in messages" 
        :key="index"
        :class="['message', msg.role === 'user' ? 'user-msg' : 'ai-msg']"
      >
        <div class="message-content">{{ msg.content }}</div>
      </div>
    </div>
    
    <div class="chat-input-area">
      <textarea 
        class="monica-chat-input"
        v-model="inputMsg" 
        @keydown.enter.prevent="sendMessage"
        @input="autoResize"
        placeholder="问我任何问题..." 
        :disabled="loading"
        ref="textareaRef"
      ></textarea>
      <button @click="sendMessage" :disabled="loading">{{ loading ? 'Sending...' : 'Send' }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import request from '../api/request';

const router = useRouter();
const inputMsg = ref('');
const loading = ref(false);
const messageListRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const messages = ref<{role: 'user' | 'ai', content: string}[]>([
  { role: 'ai', content: '你好！今天我能帮你做什么呢？' }
]);

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
  if (!inputMsg.value.trim() || loading.value) return;
  
  const userText = inputMsg.value;
  messages.value.push({ role: 'user', content: userText });
  inputMsg.value = '';
  loading.value = true;
  if (textareaRef.value) {
    textareaRef.value.style.height = '48px';
    textareaRef.value.style.overflowY = 'hidden';
  }
  await scrollToBottom();
  
  try {
    const res: any = await request.post('/assistant/chat', { question: userText });
    if (res.code === 200 && res.data) {
        messages.value.push({ role: 'ai', content: res.data.answer });
    } else {
        messages.value.push({ role: 'ai', content: `Error: ${res.message || 'Unknown error'}` });
    }
  } catch (error) {
    console.error('Failed to send message', error);
    const message = error instanceof Error ? error.message : '服务暂时不可用，请稍后重试。';
    messages.value.push({ role: 'ai', content: `Error: ${message}` });
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
};

const handleLogout = () => {
  localStorage.removeItem('satoken');
  router.push('/login');
};
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  border-left: 1px solid #eee;
  border-right: 1px solid #eee;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
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
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.message {
  max-width: 70%;
  padding: 10px 15px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.user-msg {
  align-self: flex-end;
  background-color: #42b983;
  color: white;
}
.ai-msg {
  align-self: flex-start;
  background-color: #f0f0f0;
  color: #333;
}
.chat-input-area {
  display: flex;
  padding: 15px;
  border-top: 1px solid #ddd;
  gap: 10px;
  align-items: flex-end;
}
.monica-chat-input {
  display: inline-block;
  position: relative;
  width: 100%;
  flex: 1;
  height: 48px;
  min-height: 48px;
  max-height: 144px;
  box-sizing: border-box;
  border: 1px solid rgb(34, 34, 38);
  border-radius: 8px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
  font-size: 15px;
  line-height: 24px;
  white-space: pre-wrap;
  vertical-align: bottom;
  color: rgb(34, 34, 38);
  cursor: text;
  transition: height 0.2s, border-color 0.2s;
  user-select: text;
  padding: 10px 15px;
  overflow-y: hidden;
  resize: none;
}
.monica-chat-input:hover, .monica-chat-input:focus {
  color: rgb(34, 34, 38);
  border-color: #42b983;
  outline: none;
}
.monica-chat-input:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}
.chat-input-area button {
  padding: 10px 20px;
  height: 48px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: bold;
}
.chat-input-area button:disabled {
  background-color: #a0d8b8;
  cursor: not-allowed;
}
</style>
