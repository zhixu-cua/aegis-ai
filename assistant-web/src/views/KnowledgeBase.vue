<template>
  <div class="kb-container">
    <header class="kb-header">
      <div class="nav-links">
        <router-link to="/chat" class="nav-link">Chat</router-link>
        <router-link to="/kb" class="nav-link">Knowledge Base</router-link>
      </div>
      <button @click="handleLogout" class="logout-btn">Logout</button>
    </header>

    <div class="kb-content">
      <div class="upload-section">
        <h3>Upload Document</h3>
        <div class="upload-controls">
          <input type="file" ref="fileInput" @change="handleFileChange" />
          <button @click="uploadFile" :disabled="uploading || !selectedFile">
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
        </div>
      </div>

      <div class="list-section">
        <h3>Document List</h3>
        <table class="doc-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Filename</th>
              <th>Status</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in documents" :key="doc.id">
              <td>{{ doc.id }}</td>
              <td>{{ doc.filename }}</td>
              <td>{{ doc.status }}</td>
              <td>{{ doc.createdAt }}</td>
            </tr>
            <tr v-if="documents.length === 0">
              <td colspan="4" class="empty-text">No documents found.</td>
            </tr>
          </tbody>
        </table>
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
      console.error('Failed to fetch documents:', res.message);
    }
  } catch (error) {
    console.error('Error fetching documents:', error);
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
      alert('Upload successful!');
    } else {
      alert(`Upload failed: ${res.message}`);
    }
  } catch (error) {
    console.error('Upload error:', error);
    alert('Failed to upload document.');
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
  max-width: 800px;
  margin: 0 auto;
  border-left: 1px solid #eee;
  border-right: 1px solid #eee;
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
</style>
