<template>
  <div class="sidebar" :class="{ 'is-collapsed': isCollapsed }">
    <div class="logo">
      <div class="logo-title">
        <svg v-if="!isCollapsed" class="icon aegis-logo" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L3 6V12C3 17.5 7.1 22.5 12 24C16.9 22.5 21 17.5 21 12V6L12 2Z" fill="#4f6ef7"/>
          <path d="M12 11.5L7.5 16H16.5L12 11.5Z" fill="#ffffff"/>
          <path d="M12 5.5L8.5 9H15.5L12 5.5Z" fill="#ffffff"/>
        </svg>
        <span class="text" v-if="!isCollapsed">Aegis</span>
      </div>
      <button class="collapse-btn" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? '展开边栏' : '收起边栏'">
        <svg v-if="!isCollapsed" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" class="css-i6dzq1"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
        <svg v-else viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" class="css-i6dzq1"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="15" y1="3" x2="15" y2="21"></line></svg>
      </button>
    </div>
    
    <nav class="nav">
      <div class="nav-fixed">
        <!-- Chat Section -->
        <div class="nav-section">
          <div class="nav-item-wrapper">
            <router-link to="/chat" class="nav-item" @click.prevent="handleNewChat" title="新对话">
              <span class="icon">💬</span>
              <span class="text" v-if="!isCollapsed">新对话</span>
            </router-link>
          </div>
        </div>

        <!-- KB Section -->
        <div class="nav-section mt-10">
          <router-link to="/kb" class="nav-item" title="数据源设置">
            <span class="icon">⚙️</span>
            <span class="text" v-if="!isCollapsed">数据源设置</span>
          </router-link>
        </div>

        <div class="divider"></div>

        <div class="nav-section kb-section" v-if="!isCollapsed">
          <div class="kb-header" @click="kbExpanded = !kbExpanded">
            <div class="kb-header-left">
              <span class="icon">🗂️</span>
              <span class="text">我的知识库</span>
            </div>
            <span class="arrow" :class="{ collapsed: !kbExpanded }">▼</span>
          </div>
          <div class="kb-list" v-show="kbExpanded">
            <div v-if="loading" class="kb-item empty">加载中...</div>
            <div v-else-if="myDatasources.length === 0" class="kb-item empty">暂无知识库</div>
            <div 
              v-else
              v-for="(ds, index) in myDatasources" 
              :key="ds.id" 
              class="kb-item"
              :title="ds.name"
              @click="goToKbDetail(ds.id)"
              style="cursor: pointer;"
            >
              <span class="tree-line">{{ index === myDatasources.length - 1 ? '└─' : '├─' }}</span>
              <span class="kb-name">{{ ds.name }}</span>
            </div>
          </div>
        </div>

        <!-- 共享知识库 (仅管理员可见) -->
        <div class="nav-section kb-section mt-10" v-if="!isCollapsed && userStore.role === 'admin'">
          <div class="kb-header" @click="sharedKbExpanded = !sharedKbExpanded">
            <div class="kb-header-left">
              <span class="icon">🌐</span>
              <span class="text">共享知识库</span>
            </div>
            <span class="arrow" :class="{ collapsed: !sharedKbExpanded }">▼</span>
          </div>
          <div class="kb-list" v-show="sharedKbExpanded">
            <div v-if="loading" class="kb-item empty">加载中...</div>
            <div v-else-if="sharedDatasources.length === 0" class="kb-item empty">暂无共享知识库</div>
            <div 
              v-else
              v-for="(ds, index) in sharedDatasources" 
              :key="ds.id" 
              class="kb-item"
              :title="ds.name"
              @click="goToKbDetail(ds.id)"
              style="cursor: pointer;"
            >
              <span class="tree-line">{{ index === sharedDatasources.length - 1 ? '└─' : '├─' }}</span>
              <span class="kb-name">{{ ds.name }}</span>
            </div>
          </div>
        </div>

        <div class="divider" v-if="!isCollapsed && route.path === '/chat'"></div>
      </div>

      <!-- Chat History (Only visible when on /chat and not collapsed) -->
      <div class="nav-section history-section scrollable" v-if="!isCollapsed && route.path === '/chat'">
        <div class="history-list">
          <div v-for="group in groupedSessions" :key="group.label" class="history-group">
            <div class="history-group-title">{{ group.label }}</div>
            <div 
              v-for="session in group.items" 
              :key="session.id"
              class="history-item"
              :class="{ active: chatStore.currentSessionId === session.id }"
              @click="selectSession(session.id)"
            >
              <span class="history-text" :title="session.title">{{ session.title }}</span>
              <button class="delete-btn" @click.stop="deleteSession(session.id)" title="删除对话">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" class="css-i6dzq1"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>
    
    <div class="user-container">
      <div class="user" :class="{ 'collapsed-user': isCollapsed }">
        <div class="avatar">{{ userStore.username?.[0]?.toUpperCase() || 'U' }}</div>
        <div class="user-info" v-if="!isCollapsed">
          <span class="name">{{ userStore.username || '用户名称' }}</span>
          <!-- <span class="role">{{ userStore.role || '用户' }}</span> -->
        </div>
      </div>
      <button v-if="!isCollapsed" class="logout-btn" @click="handleLogout" title="退出登录">
        <span class="icon">🚪</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import api from '@/api/request'

const userStore = useUserStore()
const chatStore = useChatStore()
const router = useRouter()
const route = useRoute()

const datasources = ref<any[]>([])
const myDatasources = computed(() => datasources.value.filter(ds => !ds.isShared))
const sharedDatasources = computed(() => datasources.value.filter(ds => ds.isShared))
const loading = ref(false)
const kbExpanded = ref(true)
const sharedKbExpanded = ref(true)
const isCollapsed = ref(false)

// Chat History Grouping
const groupedSessions = computed(() => {
  const groups: { label: string, items: any[] }[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '7天内', items: [] },
    { label: '30天内', items: [] },
    { label: '更早', items: [] }
  ]
  
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86400000
  const sevenDays = today - 86400000 * 7
  const thirtyDays = today - 86400000 * 30

  chatStore.sessions.forEach(session => {
    const time = session.updatedAt
    if (time >= today) {
      groups[0].items.push(session)
    } else if (time >= yesterday) {
      groups[1].items.push(session)
    } else if (time >= sevenDays) {
      groups[2].items.push(session)
    } else if (time >= thirtyDays) {
      groups[3].items.push(session)
    } else {
      groups[4].items.push(session)
    }
  })

  return groups.filter(g => g.items.length > 0)
})

const selectSession = async (id: string) => {
  chatStore.currentSessionId = id
  await chatStore.loadMessages(id)
}

const deleteSession = async (id: string) => {
  if (confirm('确定要删除这个对话吗？')) {
    await chatStore.deleteSession(id)
  }
}

const fetchDatasources = async () => {
  loading.value = true
  try {
    const res = await api.get('/knowledge/datasources')
    datasources.value = res.data || []
  } catch (e) {
    console.error('Failed to fetch datasources', e)
  } finally {
    loading.value = false
  }
}

const fetchUserInfo = async () => {
  try {
    const res: any = await api.get('/user/me')
    if (res.code === 200 && res.data) {
      userStore.setUsername(res.data.username)
      userStore.setUserId(res.data.id)
      userStore.setRole(res.data.role)
    }
  } catch (e) {
    console.error('Failed to fetch user info', e)
  }
}

const handleNewChat = async () => {
  if (route.path !== '/chat') {
    router.push('/chat')
  }
  chatStore.prepareNewSession()
}

const handleLogout = () => {
  localStorage.removeItem('satoken')
  router.push('/login')
}

const goToKbDetail = (id: number) => {
  router.push(`/kb-docs?id=${id}`)
}

onMounted(() => {
  fetchUserInfo()
  fetchDatasources()
  chatStore.fetchSessions().then(() => {
    if (chatStore.sessions.length > 0 && !chatStore.currentSessionId) {
      selectSession(chatStore.sessions[0].id)
    } else if (chatStore.sessions.length === 0) {
      chatStore.prepareNewSession()
    }
  })
  window.addEventListener('datasource-updated', fetchDatasources)
})
</script>

<style scoped>
.sidebar {
  width: 260px;
  min-width: 260px;
  height: 100vh;
  background: #f9f9f9;
  border-right: 1px solid #eef0f4;
  display: flex;
  flex-direction: column;
  z-index: 20;
  transition: width 0.3s ease, min-width 0.3s ease;
}

.sidebar.is-collapsed {
  width: 72px;
  min-width: 72px;
}

.logo {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 72px;
  box-sizing: border-box;
}

.is-collapsed .logo {
  padding: 20px 0;
  justify-content: center;
}

.logo-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  color: #1d2129;
}

.aegis-logo {
  width: 28px;
  height: 28px;
}

.collapse-btn {
  background: none;
  border: none;
  color: #86909c;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s;
}

.collapse-btn:hover {
  background: #eef0f4;
  color: #1d2129;
}

.nav {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.nav-fixed {
  flex-shrink: 0;
  padding: 8px 16px 0;
  display: flex;
  flex-direction: column;
  max-height: 50%;
  overflow-y: auto;
  width: 100%;
  box-sizing: border-box;
}

.is-collapsed .nav-fixed {
  padding: 8px;
  align-items: center;
}

.history-section.scrollable {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 8px;
  width: 100%;
  box-sizing: border-box;
}

.nav-section {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.mt-10 {
  margin-top: 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-radius: 8px;
  color: #1d2129;
  text-decoration: none;
  transition: all 0.2s ease;
  font-weight: 500;
  font-size: 14px;
}

.is-collapsed .nav-item {
  padding: 12px;
  justify-content: center;
  width: 44px;
  box-sizing: border-box;
}

.nav-item:hover {
  background: #f2f3f5;
}

.nav-item.router-link-active {
  background: #eef1fe;
  color: #4f6ef7;
}

.nav-item .icon {
  font-size: 18px;
}

.history-list {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0 4px;
}

.history-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-group-title {
  font-size: 12px;
  color: #86909c;
  padding: 0 12px;
  margin-bottom: 4px;
}

.history-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #4e5969;
  font-size: 14px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-item:hover {
  background: #f2f3f5;
  color: #1d2129;
}

.history-item.active {
  background: #eef1fe;
  color: #4f6ef7;
  font-weight: 500;
}

.history-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.delete-btn {
  background: none;
  border: none;
  color: #f53f3f;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: none;
  align-items: center;
  justify-content: center;
}

.delete-btn:hover {
  background: #feecea;
}

.history-item:hover .delete-btn {
  display: flex;
}

.divider {
  height: 1px;
  background: #eef0f4;
  margin: 16px 0;
  width: 100%;
}

.is-collapsed .divider {
  margin: 16px auto;
  width: 24px;
}

.kb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.2s;
}

.kb-header:hover {
  background: #f2f3f5;
}

.kb-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.arrow {
  font-size: 10px;
  color: #86909c;
  transition: transform 0.3s ease;
}

.arrow.collapsed {
  transform: rotate(-90deg);
}

.kb-list {
  display: flex;
  flex-direction: column;
  padding-left: 22px;
  margin-top: 4px;
}

.kb-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  color: #4e5969;
  font-size: 14px;
  gap: 8px;
  cursor: default;
}

.kb-item:hover {
  color: #1d2129;
}

.tree-line {
  color: #c9cdd4;
  font-family: monospace;
  font-size: 14px;
}

.kb-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty {
  color: #c9cdd4;
  font-size: 13px;
  padding-left: 12px;
}

.user-container {
  padding: 16px 20px;
  border-top: 1px solid #eef0f4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f9f9f9;
}

.is-collapsed .user-container {
  padding: 16px 0;
  justify-content: center;
}

.user {
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
}

.collapsed-user {
  justify-content: center;
}

.user .avatar {
  width: 32px;
  height: 32px;
  background: #4f6ef7;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.user-info .name {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-info .role {
  font-size: 12px;
  color: #86909c;
}

.logout-btn {
  background: none;
  border: none;
  color: #86909c;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logout-btn:hover {
  background: #fce4ec;
  color: #e53935;
}
</style>
