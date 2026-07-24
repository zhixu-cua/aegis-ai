<template>
  <div class="chat-container">
    <header class="chat-header">
      <h2>AI Chat</h2>
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
      <input 
        type="text" 
        v-model="inputMsg" 
        @keyup.enter="sendMessage"
        placeholder="Type a message..." 
        :disabled="loading"
      />
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
const messages = ref<{role: 'user' | 'ai', content: string}[]>([
  { role: 'ai', content: '你好！今天我能帮你做什么呢？' }
]);

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
  await scrollToBottom();
  
  try {
    const res: any = await request.post('/assistant/chat', { question: userText });
    if (res.code === 200 && res.data) {
        messages.value.push({ role: 'ai', content: res.data.answer });
    } else {
        messages.value.push({ role: 'ai', content: `Error: ${res.msg || 'Unknown error'}` });
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
}
.chat-input-area input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.chat-input-area input:disabled {
  background-color: #f5f5f5;
}
.chat-input-area button {
  padding: 10px 20px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.chat-input-area button:disabled {
  background-color: #a0d8b8;
  cursor: not-allowed;
}
</style>
