<template>
  <div class="knowledge-manage">
    <div class="header">
      <div class="title">
        <span class="icon">📁</span>
        <h2>数据源管理</h2>
      </div>
      <button class="btn-add" @click="showCreateDialog = true">
        + 新建数据源
      </button>
    </div>

    <div class="stats-container">
      <div class="stat-card">
        <div class="stat-icon">📄</div>
        <div class="stat-info">
          <div class="stat-label">总文档</div>
          <div class="stat-value">{{ totalDocs }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🔄</div>
        <div class="stat-info">
          <div class="stat-label">同步中</div>
          <div class="stat-value">{{ syncingCount }} 个</div>
        </div>
      </div>
      <div class="stat-card error-card">
        <div class="stat-icon">⚠️</div>
        <div class="stat-info">
          <div class="stat-label">异常</div>
          <div class="stat-value">{{ errorCount }} 个</div>
        </div>
      </div>
    </div>

    <div class="list-container">
      <div v-if="datasources.length === 0" class="empty">
        <p>暂无数据源</p>
        <p class="hint">点击右上角新建数据源开始同步文档</p>
      </div>
      <div 
        v-else
        v-for="ds in datasources" 
        :key="ds.id" 
        class="ds-card"
        @click="openConfig(ds.id)"
      >
        <div class="ds-card-header">
          <div class="ds-title">
            <span class="icon">📁</span>
            <span class="name">{{ ds.name }}</span>
          </div>
          <div class="ds-status-group">
            <div class="ds-status" :class="ds.status">
              <span class="status-dot"></span>
              {{ statusMap[ds.status] || ds.status }}
            </div>
            <button class="btn-setting" @click.stop="openConfig(ds.id)">设置</button>
          </div>
        </div>
        <div class="ds-card-body">
          <span class="ds-type">{{ ds.type === 'local' ? '本地文件夹' : (ds.type === 'confluence' ? 'Confluence' : ds.type) }}</span>
          <span class="divider">|</span>
          <span class="ds-count">{{ ds.totalDocCount || 0 }} 篇</span>
          <span class="divider">|</span>
          <span class="ds-time">最后同步：{{ formatTime(ds.lastSyncAt) }}</span>
        </div>
      </div>
    </div>

    <!-- Right Drawer for Config -->
    <div class="drawer-overlay" v-if="showConfig" @click="closeConfig"></div>
    <div class="drawer" :class="{ 'drawer-open': showConfig }">
      <div class="drawer-header">
        <h3>数据源详情</h3>
        <button class="btn-close" @click="closeConfig">✕</button>
      </div>
      <div class="drawer-content">
        <DataSourceConfig
          v-if="currentDS"
          :datasource-id="currentDS"
          @update="refresh"
        />
      </div>
    </div>

    <!-- 新建数据源对话框 -->
    <CreateDatasourceDialog
      v-model="showCreateDialog"
      @success="refresh"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useWebSocket } from '@/composables/useWebSocket'
import api from '@/api/request'
import DataSourceConfig from '@/components/DataSourceConfig.vue'
import CreateDatasourceDialog from '@/components/CreateDatasourceDialog.vue'

const route = useRoute()
const userStore = useUserStore()
const datasources = ref<any[]>([])
const currentDS = ref(null)
const showCreateDialog = ref(false)
const showConfig = ref(false)

const statusMap: Record<string, string> = {
  inactive: '未启用',
  active: '运行中',
  syncing: '同步中',
  error: '异常'
}

const totalDocs = computed(() => datasources.value.reduce((sum, ds) => sum + (ds.totalDocCount || 0), 0))
const syncingCount = computed(() => datasources.value.filter(ds => ds.status === 'syncing').length)
const errorCount = computed(() => datasources.value.filter(ds => ds.status === 'error').length)

// WebSocket 连接
const { onMessage, close } = useWebSocket(
  `/ws/knowledge/${userStore.userId}`
)

onMessage((data) => {
  // 更新对应数据源的状态
  const idx = datasources.value.findIndex(d => d.id === data.datasource_id)
  if (idx !== -1) {
    const ds = datasources.value[idx]
    ds.totalDocCount = data.total_doc_count ?? ds.totalDocCount
    ds.status = data.status ?? ds.status
    ds.lastSyncAt = data.last_sync_at ?? ds.lastSyncAt
  }
})

const refresh = async () => {
  try {
    const res = await api.get('/knowledge/datasources')
    datasources.value = res.data || []
    window.dispatchEvent(new CustomEvent('datasource-updated'))
    
    // 如果 URL 中有 id 参数，自动打开对应数据源
    if (route.query.id) {
      const id = parseInt(route.query.id as string)
      const ds = datasources.value.find((d: any) => d.id === id)
      if (ds) {
        openConfig(id)
      }
    }
  } catch (e) {
    console.error('获取知识库失败:', e)
  }
}

watch(() => route.query.id, (newId) => {
  if (newId) {
    const id = parseInt(newId as string)
    const ds = datasources.value.find((d: any) => d.id === id)
    if (ds) {
      openConfig(id)
    }
  }
})

const openConfig = (id: any) => {
  currentDS.value = id
  showConfig.value = true
}

const closeConfig = () => {
  showConfig.value = false
  setTimeout(() => {
    currentDS.value = null
  }, 300) // wait for animation
}

const formatTime = (time: any) => {
  if (!time) return '未同步'
  
  const d = new Date(time)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 2592000000) return `${Math.floor(diff / 86400000)}天前`
  
  return d.toLocaleDateString('zh-CN')
}

onMounted(() => {
  refresh()
})

onUnmounted(() => {
  close()
})
</script>

<style scoped>
.knowledge-manage {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
  padding: 24px 40px;
  overflow-y: auto;
  position: relative;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title .icon {
  font-size: 24px;
}

.title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
}

.btn-add {
  padding: 8px 16px;
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-add:hover {
  background: #3a5cd8;
}

.stats-container {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  flex: 1;
  background: #ffffff;
  border-radius: 10px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
  border: 1px solid #eef0f4;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #eef1fe;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.error-card .stat-icon {
  background: #fce4ec;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 14px;
  color: #86909c;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
}

.list-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ds-card {
  background: #ffffff;
  border-radius: 10px;
  padding: 20px 24px;
  border: 1px solid #eef0f4;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
  cursor: pointer;
  transition: all 0.2s;
}

.ds-card:hover {
  border-color: #4f6ef7;
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.1);
  transform: translateY(-2px);
}

.ds-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.ds-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}

.ds-status-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ds-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.ds-status.active {
  background: #e8f5e9;
  color: #2e7d32;
}
.ds-status.active .status-dot { background: #4caf50; }

.ds-status.syncing {
  background: #fff3e0;
  color: #e65100;
}
.ds-status.syncing .status-dot { background: #ff9800; }

.ds-status.error {
  background: #fce4ec;
  color: #c62828;
}
.ds-status.error .status-dot { background: #f44336; }

.ds-status.inactive {
  background: #f5f5f5;
  color: #616161;
}
.ds-status.inactive .status-dot { background: #9e9e9e; }

.btn-setting {
  padding: 4px 12px;
  background: #f2f3f5;
  color: #4e5969;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-setting:hover {
  background: #eef1fe;
  color: #4f6ef7;
}

.ds-card-body {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #86909c;
}

.divider {
  color: #eef0f4;
}

.empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px 0;
  color: #86909c;
  background: #fff;
  border-radius: 10px;
  border: 1px dashed #eef0f4;
}

.empty p {
  font-size: 16px;
  margin: 0;
}

.empty .hint {
  font-size: 13px;
  color: #c9cdd4;
  margin-top: 8px;
}

/* Drawer Styles */
.drawer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 100;
  animation: fadeIn 0.3s ease;
}

.drawer {
  position: fixed;
  top: 0;
  right: -600px;
  width: 600px;
  max-width: 90vw;
  height: 100vh;
  background: #fff;
  z-index: 101;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
  transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
}

.drawer-open {
  right: 0;
}

.drawer-header {
  padding: 20px 24px;
  border-bottom: 1px solid #eef0f4;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.drawer-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
}

.btn-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #86909c;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background 0.2s;
}

.btn-close:hover {
  background: #f2f3f5;
  color: #1d2129;
}

.drawer-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>