import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import request from '@/api/request';

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  citations?: string[];
  isStreaming?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([]);
  const currentSessionId = ref<string>('');

  const tempSession = ref<ChatSession>({
    id: 'temp_new_session',
    title: '新对话',
    messages: [{ role: 'ai', content: '您好！我是您的智能助手，有什么可以帮助您？' }],
    updatedAt: Date.now()
  });

  const currentSession = computed(() => {
    if (currentSessionId.value === 'temp_new_session') {
      return tempSession.value;
    }
    return sessions.value.find(s => s.id === currentSessionId.value);
  });

  const fetchSessions = async () => {
    try {
      const res: any = await request.get('/assistant/sessions');
      if (res.code === 200 && res.data) {
        sessions.value = res.data.map((s: any) => ({
          id: s.id.toString(),
          title: s.sessionTitle,
          updatedAt: new Date(s.lastActiveTime).getTime(),
          messages: []
        }));
      }
    } catch (e) {
      console.error('Failed to fetch sessions', e);
    }
  };

  const prepareNewSession = () => {
    tempSession.value = {
      id: 'temp_new_session',
      title: '新对话',
      messages: [{ role: 'ai', content: '您好！我是您的智能助手，有什么可以帮助您？' }],
      updatedAt: Date.now()
    };
    currentSessionId.value = 'temp_new_session';
  };

  const createRealSession = async (title: string = '新对话') => {
    try {
      const res: any = await request.post('/assistant/sessions', { sessionTitle: title });
      if (res.code === 200 && res.data) {
        const newSession: ChatSession = {
          id: res.data.id.toString(),
          title: res.data.sessionTitle,
          messages: [...tempSession.value.messages],
          updatedAt: new Date(res.data.lastActiveTime).getTime()
        };
        sessions.value.unshift(newSession);
        currentSessionId.value = newSession.id;
        return newSession.id;
      }
    } catch (e) {
      console.error('Failed to create session', e);
    }
    return null;
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
          if (session.messages.length === 0) {
            session.messages.push({ role: 'ai', content: '您好！我是您的智能助手，有什么可以帮助您？' });
          }
        }
      }
    } catch (e) {
      console.error('Failed to load messages', e);
    }
  };

  const deleteSession = async (id: string) => {
    try {
      const res: any = await request.delete(`/assistant/sessions/${id}`);
      if (res.code === 200) {
        sessions.value = sessions.value.filter(s => s.id !== id);
        if (currentSessionId.value === id) {
          if (sessions.value.length > 0) {
            currentSessionId.value = sessions.value[0].id;
            await loadMessages(currentSessionId.value);
          } else {
            currentSessionId.value = '';
          }
        }
        return true;
      }
    } catch (e) {
      console.error('Failed to delete session', e);
    }
    return false;
  };

  return {
    sessions,
    currentSessionId,
    currentSession,
    fetchSessions,
    prepareNewSession,
    createRealSession,
    loadMessages,
    deleteSession
  };
});
