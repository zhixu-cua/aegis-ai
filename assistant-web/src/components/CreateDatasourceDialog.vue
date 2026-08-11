<template>
  <div v-if="visible" class="dialog-overlay" @click.self="close">
    <div class="dialog">
      <div class="dialog-header">
        <h3>新建知识库</h3>
        <button class="btn-close" @click="close">×</button>
      </div>
      <div class="dialog-body">
        <div class="form-group">
          <label>名称 *</label>
          <input v-model="form.name" placeholder="如：2024年产品手册" />
        </div>
        <div class="form-group">
          <label>数据源类型 *</label>
          <select v-model="form.sourceType">
            <option value="local">本地文件夹</option>
            <option value="cos">腾讯云 COS</option>
          </select>
        </div>
        <template v-if="form.sourceType === 'local'">
          <div class="form-group">
            <label>文件夹路径 *</label>
            <input v-model="form.path" placeholder="/data/knowledge/product" />
          </div>
        </template>
        <template v-if="form.sourceType === 'cos'">
          <div class="form-group">
            <label>COS桶名 *</label>
            <input v-model="form.bucket" placeholder="examplebucket-1250000000" />
          </div>
          <div class="form-group">
            <label>所属地域 *</label>
            <input v-model="form.region" placeholder="ap-guangzhou" />
          </div>
          <div class="form-group">
            <label>SecretId *</label>
            <input v-model="form.secretId" placeholder="AKID..." />
          </div>
          <div class="form-group">
            <label>SecretKey *</label>
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
      </div>
      <div class="dialog-footer">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" @click="submit" :disabled="loading">
          {{ loading ? '创建中...' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import api from '@/api/request'

const props = defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = ref(false)
const loading = ref(false)
const form = ref<any>({
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

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (!val) {
    // 重置表单
    form.value = {
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
    }
  }
})

const close = () => {
  emit('update:modelValue', false)
}

const submit = async () => {
  if (!form.value.name) {
    alert('请填写知识库名称')
    return
  }
  
  if (form.value.sourceType === 'local' && !form.value.path) {
    alert('请填写本地文件夹路径')
    return
  }

  if (form.value.sourceType === 'cos') {
    if (!form.value.bucket || !form.value.region || !form.value.secretId || !form.value.secretKey) {
      alert('请填写完整的 COS 配置信息（桶名、地域、SecretId、SecretKey）')
      return
    }
  }

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
    await api.post('/knowledge/datasource', {
      name: form.value.name,
      sourceType: form.value.sourceType,
      sourceConfig: JSON.stringify(config),
      syncFrequency: form.value.syncFrequency,
      sourceRank: form.value.sourceRank
    })
    emit('success')
    close()
  } catch (e: any) {
    console.error(e)
    alert('创建失败：' + (e.response?.data?.message || e.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.dialog {
  background: #fff;
  border-radius: 16px;
  width: 520px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e8ecf1;
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #86909c;
}

.btn-close:hover {
  color: #1d2129;
}

.dialog-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.dialog-body .form-group {
  margin-bottom: 16px;
}

.dialog-body .form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  color: #4e5969;
}

.dialog-body .form-group input,
.dialog-body .form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 14px;
}

.dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid #e8ecf1;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-secondary {
  padding: 8px 20px;
  background: #f5f7fa;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  cursor: pointer;
}

.btn-secondary:hover {
  background: #e8ecf1;
}

.btn-primary {
  padding: 8px 20px;
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  background: #3a5cd8;
}
</style>
