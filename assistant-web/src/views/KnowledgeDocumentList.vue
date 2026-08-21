<template>
  <div class="kb-docs-container">
    <div class="header">
      <h2>{{ datasource?.name || '知识库文档' }}</h2>
      <div class="header-actions">
        
        <label v-if="datasource?.sourceType !== 'local'" class="btn btn-primary upload-btn" :class="{ 'disabled': uploading }" title="支持格式: .txt, .md, .pdf, .docx, .doc, .xlsx, .xls, .csv, .png, .jpg, .jpeg, .html, .htm">
          <input type="file" @change="handleUpload" accept=".txt,.md,.pdf,.docx,.doc,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.html,.htm" hidden multiple :disabled="uploading" />
          <span>{{ uploading ? '上传中...' : '上传文件' }}</span>
        </label>
        <button class="btn btn-outline" @click="goBack">返回</button>
      </div>
    </div>
    
    <div class="document-list">
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
            <td>{{ doc.filePath?.split('/').pop() || doc.fileName }}</td>
            <td>
              <span class="doc-status" :class="doc.status">
                {{ docStatusMap[doc.status] || doc.status }}
              </span>
            </td>
            <td>{{ doc.chunkCount || 0 }}</td>
            <td>{{ formatTime(doc.processedAt) }}</td>
            <td>
              <button class="btn btn-sm btn-danger" @click="handleDeleteDoc(doc.id)" :disabled="loading">
                删除
              </button>
            </td>
          </tr>
          <tr v-if="documents.length === 0">
            <td colspan="5" class="empty-td">暂无文档</td>
          </tr>
        </tbody>
      </table>
      
      <!-- 简单的分页控件 -->
      <div class="pagination" v-if="totalPages > 0">
        <div class="page-size">
          每页展示：
          <select v-model="pageSize" @change="onPageSizeChange">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
          条
        </div>
        <div class="page-controls">
          <button @click="changePage(currentPage - 1)" :disabled="currentPage <= 1 || loading">上一页</button>
          <span>{{ currentPage }} / {{ totalPages }}</span>
          <button @click="changePage(currentPage + 1)" :disabled="currentPage >= totalPages || loading">下一页</button>
        </div>
        <div class="page-total">共 {{ totalElements }} 条</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/request'

const route = useRoute()
const router = useRouter()

const datasourceId = ref<number | null>(null)
const datasource = ref<any>({})
const documents = ref<any[]>([])
const loading = ref(false)
const uploading = ref(false)

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)
const totalElements = ref(0)
const totalPages = ref(0)

const docStatusMap: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
  deleted: '已删除'
}

const loadDatasourceInfo = async () => {
  if (!datasourceId.value) return
  try {
    const res: any = await api.get(`/knowledge/datasource/${datasourceId.value}`)
    if (res.code === 200) {
      datasource.value = res.data
    }
  } catch (e) {
    console.error(e)
  }
}

const loadDocuments = async () => {
  if (!datasourceId.value) return
  loading.value = true
  try {
    const res: any = await api.get(`/knowledge/datasource/${datasourceId.value}/documents`, {
      params: {
        page: currentPage.value,
        size: pageSize.value
      }
    })
    if (res.code === 200) {
      // 兼容 PageResult 结构
      if (res.data && res.data.content) {
        documents.value = res.data.content
        totalElements.value = res.data.totalElements || 0
        totalPages.value = res.data.totalPages || 0
      } else if (res.data && res.data.records) { // 其他常见分页格式
        documents.value = res.data.records
        totalElements.value = res.data.total || 0
        totalPages.value = Math.ceil(totalElements.value / pageSize.value)
      } else if (Array.isArray(res.data)) {
        // 如果后端还没改为分页，兼容旧数组
        documents.value = res.data
        totalElements.value = res.data.length
        totalPages.value = 1
      }
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const changePage = (page: number) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    loadDocuments()
  }
}

const onPageSizeChange = () => {
  currentPage.value = 1
  loadDocuments()
}

const handleUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (!target.files || target.files.length === 0) return;
  
  if (datasource.value?.sourceType !== 'cos') {
    alert('当前数据源不支持 COS 上传');
    target.value = '';
    return;
  }

  const validExtensions = ['.txt', '.md', '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.png', '.jpg', '.jpeg', '.html', '.htm'];
  const filesArray = Array.from(target.files);
  const invalidFiles = filesArray.filter(file => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    return !validExtensions.includes(ext);
  });

  if (invalidFiles.length > 0) {
    alert(`包含不支持的文件格式，仅支持: ${validExtensions.join(', ')}`);
    target.value = '';
    return;
  }

  uploading.value = true;
  let successCount = 0;
  let failCount = 0;

  try {
    for (const file of filesArray) {
      const formData = new FormData();
      formData.append('file', file);
      
      try {
        const res: any = await api.post(`/knowledge/datasource/${datasourceId.value}/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        if (res.code === 200) {
          successCount++;
        } else {
          failCount++;
          console.error(`上传失败 ${file.name}:`, res.message);
        }
      } catch (err) {
        failCount++;
        console.error(`上传失败 ${file.name}:`, err);
      }
    }
    
    alert(`上传完成: 成功 ${successCount} 个, 失败 ${failCount} 个`);
    // 上传完成后，重新加载文档列表并触发全局事件刷新数据源统计
    await loadDocuments();
    await loadDatasourceInfo();
    window.dispatchEvent(new CustomEvent('datasource-updated'));
  } finally {
    uploading.value = false;
    target.value = '';
  }
}

const handleDeleteDoc = async (docId: number) => {
  if (!confirm('确定要物理删除该文档及其切片数据吗？删除后不可恢复。')) return
  loading.value = true
  try {
    const res: any = await api.delete(`/knowledge/datasource/${datasourceId.value}/documents/${docId}`)
    if (res.code === 200) {
      alert('删除成功，后台将自动清理数据')
      // 刷新列表和统计
      await loadDocuments()
      await loadDatasourceInfo()
      // 触发全局事件通知左侧边栏等刷新
      window.dispatchEvent(new CustomEvent('datasource-updated'))
    } else {
      alert(`删除失败: ${res.message || '未知错误'}`)
    }
  } catch (e) {
    console.error(e)
    alert('删除失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/kb')
}

const formatTime = (time: any) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const init = () => {
  const id = parseInt(route.query.id as string)
  if (!isNaN(id)) {
    datasourceId.value = id
    currentPage.value = 1
    loadDatasourceInfo()
    loadDocuments()
  }
}

watch(() => route.query.id, () => {
  init()
})

onMounted(() => {
  init()
})
</script>

<style scoped>
.kb-docs-container {
  padding: 24px 40px;
  background: #f5f7fa;
  height: 100%;
  overflow-y: auto;
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
  color: #1d2129;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background-color: #4f6ef7;
  color: #ffffff;
}

.btn-primary:hover:not(:disabled):not(.disabled) {
  background-color: #3a5cd8;
}

.btn-primary.disabled {
  background-color: #b2c1ff;
  cursor: not-allowed;
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
  background: transparent;
  color: #f53f3f;
  border: 1px solid #f53f3f;
}
.btn-danger:hover:not(:disabled) {
  background: #fce4ec;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.document-list {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e8ecf1;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th {
  text-align: left;
  padding: 10px 12px;
  color: #86909c;
  font-weight: 500;
  border-bottom: 1px solid #e8ecf1;
}

td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f2f5;
}

.doc-status.completed { color: #00b42a; }
.doc-status.processing { color: #f77200; }
.doc-status.failed { color: #f53f3f; }
.doc-status.pending { color: #86909c; }
.doc-status.deleted { color: #c9cdd4; }

.empty-td {
  text-align: center;
  color: #c9cdd4;
  padding: 40px 0 !important;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  font-size: 14px;
  color: #4e5969;
}

.page-size select {
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #d0d5dd;
  margin: 0 4px;
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-controls button {
  padding: 6px 12px;
  border: 1px solid #d0d5dd;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  color: #1d2129;
}

.page-controls button:hover:not(:disabled) {
  background: #f2f3f5;
}

.page-controls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
