<template>
  <div class="kb-container">
    <header class="kb-header">
      <div class="nav-links">
        <router-link to="/chat" class="nav-link">聊天</router-link>
        <router-link to="/kb" class="nav-link">知识库</router-link>
      </div>
      <button @click="handleLogout" class="logout-btn">退出</button>
    </header>

    <div class="kb-content">
      <div class="upload-section">
        <h3>上传文档</h3>
        <div class="upload-controls">
          <input type="file" ref="fileInput" @change="handleFileChange" accept=".txt,.md,.pdf,.docx,.doc,.xlsx,.xls,.png,.jpg" />
          <button @click="uploadFile" :disabled="uploading || !selectedFile">
            {{ uploading ? 'Uploading...' : '上传' }}
          </button>
        </div>
      </div>

      <div class="list-section">
        <h3>文档列表</h3>
        <div class="table-responsive">
          <table class="doc-table">
            <thead>
              <tr>
                <th>序号</th>
                <th>文件名</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(doc, index) in documents" :key="doc.id">
                <td>{{ index + 1 }}</td>
                <td>{{ doc.fileName }}</td>
                <td>
                  <span :class="['status-badge', doc.status?.toLowerCase()]">
                    {{ getStatusText(doc.status) }}
                  </span>
                </td>
                <td>{{ doc.uploadTime }}</td>
                <td>
                  <button class="delete-btn" @click="deleteDocument(doc.id)">删除</button>
                </td>
              </tr>
              <tr v-if="documents.length === 0">
                <td colspan="5" class="empty-text">暂无文档</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import request from '../api/request';

const router = useRouter();
const documents = ref<any[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const uploading = ref(false);

const statusDict: Record<string, string> = {
  'PENDING': '处理中',
  'SUCCESS': '已完成',
  'FAILED': '失败'
};

const getStatusText = (status: string) => {
  if (!status) return '未知';
  return statusDict[status.toUpperCase()] || status;
};

const deleteDocument = async (id: number) => {
  if (!confirm('确定要删除该文档吗？')) return;
  
  try {
    const res: any = await request.delete(`/kb/${id}`);
    if (res.code === 200) {
      await fetchDocuments();
    } else {
      alert(`删除失败: ${res.message}`);
    }
  } catch (error) {
    console.error('Delete error:', error);
    alert('删除文档时发生错误');
  }
};

const handleLogout = () => {
  localStorage.removeItem('satoken');
  router.push('/login');
};

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
  } else {
    selectedFile.value = null;
  }
};

const fetchDocuments = async () => {
  try {
    const res: any = await request.get('/kb/list');
    if (res.code === 200) {
      documents.value = res.data || [];
    } else {
      console.error('获取文档列表失败:', res.message);
      alert('获取文档列表失败');
    }
  } catch (error) {
    console.error('获取文档列表失败:', error);
    alert('获取文档列表失败');
  }
};

const uploadFile = async () => {
  if (!selectedFile.value) return;

  uploading.value = true;
  const formData = new FormData();
  formData.append('file', selectedFile.value);

  try {
    const res: any = await request.post('/kb/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    if (res.code === 200) {
      if (fileInput.value) {
        fileInput.value.value = '';
      }
      selectedFile.value = null;
      await fetchDocuments();
      alert('上传成功');
    } else {
      alert(`上传失败: ${res.message}`);
    }
  } catch (error) {
    console.error('上传文档时发生错误:', error);
    alert('上传文档时发生错误');
  } finally {
    uploading.value = false;
  }
};

onMounted(() => {
  fetchDocuments();
});
</script>

<style scoped>
.kb-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  max-width: 100%;
  margin: 0;
  padding: 0;
  background-color: #fafafa;
}

.kb-header {
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

.kb-content {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.upload-section {
  margin-bottom: 30px;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background-color: #fafafa;
}

.upload-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
}

.upload-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.upload-controls input[type="file"] {
  flex: 1;
}

.upload-controls button {
  padding: 8px 20px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.upload-controls button:disabled {
  background-color: #a0d8b8;
  cursor: not-allowed;
}

.list-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
}

.doc-table th, .doc-table td {
  border: 1px solid #ddd;
  padding: 12px;
  text-align: left;
}

.doc-table th {
  background-color: #f5f5f5;
  font-weight: bold;
}

.empty-text {
  text-align: center !important;
  color: #888;
  padding: 20px !important;
}

.status-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.pending { background-color: #e6f7ff; color: #1890ff; border: 1px solid #91d5ff; }
.status-badge.success { background-color: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
.status-badge.failed { background-color: #fff2f0; color: #f5222d; border: 1px solid #ffccc7; }

.delete-btn {
  padding: 4px 10px;
  background-color: transparent;
  color: #ff4d4f;
  border: 1px solid #ff4d4f;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
}
.delete-btn:hover {
  background-color: #ff4d4f;
  color: white;
}

@media (max-width: 768px) {
  .kb-container {
    border: none;
  }
  .upload-controls {
    flex-direction: column;
    align-items: stretch;
  }
  .doc-table th, .doc-table td {
    padding: 8px;
    font-size: 14px;
    white-space: nowrap;
  }
}
</style>
