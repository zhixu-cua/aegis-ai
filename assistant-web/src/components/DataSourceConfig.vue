<template>
  <div class="datasource-config">
    <div class="header">
      <h2>{{ datasource.name }}</h2>
      <div class="actions">
        <button 
          class="btn btn-primary" 
          @click="toggleSync"
          :disabled="loading"
        >
          {{ datasource.status === 'active' ? '⏸ 暂停同步' : '▶ 启用同步' }}
        </button>
        <button class="btn btn-outline" @click="handleRefresh" :disabled="loading">
          🔄 强制刷新
        </button>
      </div>
    </div>
    
    <!-- 状态看板 -->
    <div class="dashboard">
      <div class="stat-item">
        <span class="label">📄 文档总数</span>
        <span class="value">{{ datasource.totalDocCount || 0 }}</span>
      </div>
      <div class="stat-item">
        <span class="label">🔄 同步状态</span>
        <span class="value" :class="datasource.status">
          {{ statusMap[datasource.status] }}
        </span>
      </div>
      <div class="stat-item">
        <span class="label">⏱ 最后同步</span>
        <span class="value">{{ formatTime(datasource.lastSyncAt) }}</span>
      </div>
    </div>
    
    <!-- 配置表单 -->
    <div class="config-form">
      <h4>数据源配置</h4>
      <div class="form-group">
        <label>名称</label>
        <input v-model="form.name" placeholder="请输入知识库名称" />
      </div>
      <div class="form-group">
        <label>数据源类型</label>
        <select v-model="form.sourceType">
          <option value="local">本地文件夹</option>
          <option value="cos">腾讯云 COS</option>
          <option value="confluence">Confluence</option>
          <option value="network_share">网络共享盘</option>
        </select>
      </div>
      
      <!-- 不同源的不同配置 -->
      <template v-if="form.sourceType === 'local'">
        <div class="form-group">
          <label>文件夹路径</label>
          <input v-model="form.path" placeholder="如：/data/knowledge/product" />
        </div>
      </template>
      
      <template v-if="form.sourceType === 'cos'">
        <div class="form-group">
          <label>Bucket 名称</label>
          <input v-model="form.bucket" placeholder="examplebucket-1250000000" />
        </div>
        <div class="form-group">
          <label>Region</label>
          <input v-model="form.region" placeholder="ap-guangzhou" />
        </div>
        <div class="form-group">
          <label>SecretId</label>
          <input v-model="form.secretId" placeholder="AKID..." />
        </div>
        <div class="form-group">
          <label>SecretKey</label>
          <input type="password" v-model="form.secretKey" placeholder="输入您的 SecretKey" />
        </div>
        <div class="form-group">
          <label>前缀路径</label>
          <input v-model="form.prefix" placeholder="product_manual/" />
        </div>
      </template>
      
      <div class="form-group">
        <label>同步频率</label>
        <select v-model="form.syncFrequency">
          <option value="realtime">实时同步</option>
          <option value="hourly">每小时</option>
          <option value="daily">每天</option>
        </select>
      </div>
      
      <div class="form-group">
        <label>信任度权重 (1-10)</label>
        <input type="number" v-model="form.sourceRank" min="1" max="10" />
      </div>
      
      <button class="btn btn-save" @click="saveConfig" :disabled="loading">
        💾 保存配置
      </button>
    </div>
    
    <!-- 文档列表 -->
    <div class="document-list">
      <h4>文档列表</h4>
      <table>
        <thead>
          <tr>
            <th>文件名</th>
            <th>状态</th>
            <th>切块数</th>
            <th>处理时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in documents" :key="doc.id">
            <td>{{ doc.filePath.split('/').pop() }}</td>
            <td>
              <span class="doc-status" :class="doc.status">
                {{ docStatusMap[doc.status] }}
              </span>
            </td>
            <td>{{ doc.chunkCount || 0 }}</td>
            <td>{{ formatTime(doc.processedAt) }}</td>
            <td>
              <button class="btn btn-outline btn-sm btn-danger" @click="handleDeleteDoc(doc.id)" :disabled="loading">
                删除
              </button>
            </td>
          </tr>
          <tr v-if="documents.length === 0">
            <td colspan="5" class="empty-td">暂无文档</td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 问答验证 -->
    <div class="verify-section">
      <h4>🔍 验证知识库</h4>
      <div class="verify-input">
        <input 
          v-model="verifyQuestion" 
          placeholder="输入问题测试文档是否生效..."
          @keyup.enter="doVerify"
        />
        <button @click="doVerify" :disabled="verifying">发送</button>
      </div>
      <div v-if="verifyAnswer" class="verify-answer">
        <strong>🤖 回答：</strong>
        <span>{{ verifyAnswer }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import api from '@/api/request'

const props = defineProps({
  datasourceId: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['update'])

const loading = ref(false)
const verifying = ref(false)
const datasource = ref<any>({})
const documents = ref<any[]>([])
const verifyQuestion = ref('')
const verifyAnswer = ref('')

const form = ref({
  name: '',
  sourceType: 'local',
  path: '',
  bucket: '',
  region: '',
  secretId: '',
  secretKey: '',
  prefix: '',
  syncFrequency: 'realtime',
  sourceRank: 5
})

const statusMap: Record<string, string> = {
  inactive: '未启用',
  active: '运行中',
  syncing: '同步中',
  error: '异常'
}

const docStatusMap: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
  deleted: '已删除'
}

const loadData = async () => {
  loading.value = true
  try {
    const [detailRes, docsRes] = await Promise.all([
      api.get(`/knowledge/datasource/${props.datasourceId}`),
      api.get(`/knowledge/datasource/${props.datasourceId}/documents`)
    ])
    datasource.value = detailRes.data
    
    // 兼容后端返回的是 Page 对象还是旧的 List 数组
    const docsData = docsRes.data
    if (docsData && docsData.content) {
      documents.value = docsData.content
    } else if (docsData && docsData.records) {
      documents.value = docsData.records
    } else if (Array.isArray(docsData)) {
      documents.value = docsData
    } else {
      documents.value = []
    }
    
    // 填充表单
    form.value.name = datasource.value.name || ''
    form.value.sourceType = datasource.value.sourceType || 'local'
    form.value.syncFrequency = datasource.value.syncFrequency || 'realtime'
    form.value.sourceRank = datasource.value.sourceRank || 5
    
    const config = datasource.value.sourceConfig || {}
    if (form.value.sourceType === 'local') {
      form.value.path = config.path || ''
    } else if (form.value.sourceType === 'cos') {
      form.value.bucket = config.bucket || ''
      form.value.region = config.region || ''
      form.value.secretId = config.secretId || ''
      form.value.secretKey = config.secretKey || ''
      form.value.prefix = config.prefix || ''
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const toggleSync = async () => {
  loading.value = true
  try {
    const action = datasource.value.status === 'active' ? 'disable' : 'enable'
    await api.post(`/knowledge/datasource/${props.datasourceId}/sync/${action}`)
    await loadData()
    emit('update')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleDeleteDoc = async (docId: number) => {
  if (!confirm('确定要删除该文档吗？')) return
  loading.value = true
  try {
    await api.delete(`/knowledge/datasource/${props.datasourceId}/documents/${docId}`)
    await loadData()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  // 自动获取配置的路径
  let path = ''
  if (form.value.sourceType === 'local') {
    path = form.value.path
  } else if (form.value.sourceType === 'cos') {
    path = form.value.prefix || ''
  } else {
    path = '' // 默认或者其他类型的兜底
  }
  
  if (form.value.sourceType === 'local' && !path) {
    alert('请先配置并保存路径信息')
    return
  }
  
  loading.value = true
  try {
    await api.post(`/knowledge/datasource/${props.datasourceId}/refresh`, null, {
      params: { filePath: path }
    })
    alert('已发送强制刷新请求')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  loading.value = true
  try {
    const config: any = {}
    if (form.value.sourceType === 'local') {
      config.path = form.value.path
    } else if (form.value.sourceType === 'cos') {
      config.bucket = form.value.bucket
      config.region = form.value.region
      config.secretId = form.value.secretId
      config.secretKey = form.value.secretKey
      config.prefix = form.value.prefix || ''
    }

    const payload = {
      name: form.value.name,
      sourceConfig: JSON.stringify(config),
      syncFrequency: form.value.syncFrequency,
      sourceRank: form.value.sourceRank
    }
    
    await api.put(`/knowledge/datasource/${props.datasourceId}`, payload)
    alert('保存成功')
    await loadData()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const doVerify = async () => {
  if (!verifyQuestion.value.trim()) return
  verifying.value = true
  verifyAnswer.value = ''
  try {
    // 使用现有的 RAG 接口
    const response = await fetch('/api/assistant/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        question: verifyQuestion.value,
        datasourceId: props.datasourceId  // 限定检索范围
      })
    })
    // 流式读取
    if (!response.body) throw new Error('No response body')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let answer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      // 解析 SSE 格式
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.content) {
              answer += data.content
              verifyAnswer.value = answer
            }
          } catch (e) {}
        }
      }
    }
  } catch (e) {
    console.error(e)
    verifyAnswer.value = '验证失败，请稍后重试'
  } finally {
    verifying.value = false
  }
}

const formatTime = (time: any) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

watch(() => props.datasourceId, loadData, { immediate: true })
</script>

<style scoped>
.datasource-config {
  max-width: 900px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h2 {
  margin: 0;
  font-size: 22px;
}

.actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background: #4f6ef7;
  color: #fff;
}
.btn-primary:hover:not(:disabled) {
  background: #3a5cd8;
}

.btn-outline {
  background: transparent;
  border: 1px solid #d0d5dd;
  color: #1d2129;
}
.btn-outline:hover:not(:disabled) {
  background: #f5f7fa;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-danger {
  color: #f53f3f;
  border-color: #f53f3f;
}
.btn-danger:hover:not(:disabled) {
  background: #fce4ec;
}

.btn-save {
  background: #00b42a;
  color: #fff;
  padding: 10px 32px;
  font-size: 16px;
}
.btn-save:hover:not(:disabled) {
  background: #009a24;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.dashboard {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  background: #f7f8fa;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-item .label {
  font-size: 13px;
  color: #86909c;
}

.stat-item .value {
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
}

.stat-item .value.active {
  color: #00b42a;
}
.stat-item .value.syncing {
  color: #f77200;
}
.stat-item .value.error {
  color: #f53f3f;
}

.config-form {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  border: 1px solid #e8ecf1;
}

.config-form h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  color: #4e5969;
}

.form-group input,
.form-group select {
  width: 100%;
  max-width: 500px;
  padding: 8px 12px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #4f6ef7;
}

.document-list {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  border: 1px solid #e8ecf1;
}

.document-list h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
}

.document-list table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.document-list th {
  text-align: left;
  padding: 10px 12px;
  color: #86909c;
  font-weight: 500;
  border-bottom: 1px solid #e8ecf1;
}

.document-list td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f2f5;
}

.doc-status.completed {
  color: #00b42a;
}
.doc-status.processing {
  color: #f77200;
}
.doc-status.failed {
  color: #f53f3f;
}
.doc-status.pending {
  color: #86909c;
}
.doc-status.deleted {
  color: #c9cdd4;
}

.empty-td {
  text-align: center;
  color: #c9cdd4;
  padding: 40px 0 !important;
}

.verify-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e8ecf1;
}

.verify-section h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
}

.verify-input {
  display: flex;
  gap: 12px;
}

.verify-input input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 14px;
}

.verify-input input:focus {
  outline: none;
  border-color: #4f6ef7;
}

.verify-input button {
  padding: 10px 24px;
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.verify-input button:hover:not(:disabled) {
  background: #3a5cd8;
}

.verify-answer {
  margin-top: 16px;
  padding: 16px 20px;
  background: #f7f8fa;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
}
</style>
