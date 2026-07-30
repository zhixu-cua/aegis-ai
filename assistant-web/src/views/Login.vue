<template>
  <div class="login-wrapper">
    <!-- 如果注册成功，显示一个优雅的全屏成功提示罩层 -->
    <div v-if="registerSuccess" class="success-overlay">
      <div class="success-card">
        <div class="success-icon">
          <svg viewBox="0 0 24 24" width="48" height="48" stroke="#42b983" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <h2>注册成功！</h2>
        <p>欢迎加入 Aegis AI，您的账号已准备就绪。</p>
        <div class="success-actions">
          <button @click="enterSystem" class="enter-btn">进入系统</button>
          <button @click="backToLogin" class="back-btn">返回登录</button>
        </div>
      </div>
    </div>

    <div class="login-card" v-show="!registerSuccess">
      <div class="login-left">
        <div class="brand-content">
          <h1>Aegis AI</h1>
          <p>智能网站群售后助手</p>
          <div class="features">
            <span>✨ 语义混合检索</span>
            <span>📚 专属知识库</span>
            <span>⚡️ 极速响应解答</span>
          </div>
        </div>
      </div>
      <div class="login-right">
        <div class="form-header">
          <h2>{{ isRegister ? '创建账号' : '欢迎回来' }}</h2>
          <p>{{ isRegister ? '注册以开始使用您的专属 AI 助手' : '请登录以继续访问您的工作台' }}</p>
        </div>
        
        <form @submit.prevent="handleSubmit" class="login-form">
          <div class="form-group">
            <label for="username">用户名</label>
            <div class="input-wrapper">
              <input 
                type="text" 
                id="username" 
                v-model="username" 
                placeholder="请输入用户名"
                required 
                :class="{ 'has-error': error }"
              />
            </div>
          </div>
          
          <div class="form-group">
            <label for="password">密码</label>
            <div class="input-wrapper">
              <input 
                type="password" 
                id="password" 
                v-model="password" 
                placeholder="请输入密码"
                required 
                :class="{ 'has-error': error }"
              />
            </div>
          </div>

          <div v-if="error" class="error-msg">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            {{ error }}
          </div>
          
          <button type="submit" class="submit-btn" :disabled="loading">
            <span v-if="loading" class="loader"></span>
            <span v-else>{{ isRegister ? '注册' : '登录' }}</span>
          </button>
          
          <div class="toggle-mode">
            <span v-if="!isRegister">还没有账号？ <a href="#" @click.prevent="toggleMode">立即注册</a></span>
            <span v-else>已有账号？ <a href="#" @click.prevent="toggleMode">立即登录</a></span>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import request from '../api/request';

const username = ref('');
const password = ref('');
const error = ref('');
const loading = ref(false);
const isRegister = ref(false);
const registerSuccess = ref(false);
const router = useRouter();

const toggleMode = () => {
  isRegister.value = !isRegister.value;
  error.value = '';
  username.value = '';
  password.value = '';
};

// 返回手动登录
const backToLogin = () => {
  registerSuccess.value = false;
  isRegister.value = false;
  password.value = ''; // 清空密码让用户重输，保留用户名
};

// 注册成功后直接进入系统（自动执行一次登录）
const enterSystem = async () => {
  registerSuccess.value = false;
  isRegister.value = false;
  await handleSubmit(); 
};

const handleSubmit = async () => {
  error.value = '';
  loading.value = true;
  try {
    const endpoint = isRegister.value ? '/user/doRegister' : '/user/doLogin';
    const res: any = await request.post(endpoint, {
      username: username.value,
      password: password.value
    });
    
    if (res.code === 200) {
      if (isRegister.value) {
        // 注册成功后，显示成功交互界面
        registerSuccess.value = true;
      } else {
        // 登录成功
        if (res.data && res.data.tokenValue) {
          localStorage.setItem('satoken', res.data.tokenValue);
        } else if (res.data && typeof res.data === 'string') {
          localStorage.setItem('satoken', res.data);
        }
        router.push('/chat');
      }
    } else {
      // 准确展示后端返回的错误信息（如“用户名已存在”、“用户名或密码不能为空”等）
      // 如果后端没返回，才给出一个默认兜底提示
      error.value = res.msg || res.message || (isRegister.value ? '注册失败，请检查输入' : '登录失败，请检查账号密码');
    }
  } catch (err: any) {
    // 捕获网络异常或服务端 500 等错误，并尽可能提取准确的信息
    error.value = err.response?.data?.msg || err.response?.data?.message || err.message || (isRegister.value ? '注册请求失败，请检查网络或联系管理员' : '登录请求失败，请检查网络或联系管理员');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f4f8 0%, #e6f6ef 100%);
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  box-sizing: border-box;
}

.login-card {
  display: flex;
  width: 100%;
  max-width: 900px;
  min-height: 500px;
  background: #ffffff;
  border-radius: 24px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

/* 左侧品牌区 */
.login-left {
  flex: 1;
  background: linear-gradient(135deg, #42b983 0%, #2c8c61 100%);
  color: white;
  padding: 60px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.login-left::before {
  content: "";
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
  transform: rotate(30deg);
  pointer-events: none;
}

.brand-content {
  position: relative;
  z-index: 1;
}

.brand-content h1 {
  font-size: 2.5rem;
  font-weight: 800;
  margin: 0 0 10px 0;
  letter-spacing: 1px;
}

.brand-content p {
  font-size: 1.2rem;
  opacity: 0.9;
  margin: 0 0 40px 0;
}

.features {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.features span {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.05rem;
  background: rgba(255, 255, 255, 0.15);
  padding: 12px 20px;
  border-radius: 12px;
  backdrop-filter: blur(10px);
  width: fit-content;
}

/* 右侧表单区 */
.login-right {
  flex: 1;
  padding: 60px 50px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #ffffff;
}

.form-header {
  margin-bottom: 40px;
}

.form-header h2 {
  font-size: 2rem;
  color: #1a1a1a;
  margin: 0 0 8px 0;
  font-weight: 700;
}

.form-header p {
  color: #666;
  margin: 0;
  font-size: 1rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 0.95rem;
  color: #333;
  font-weight: 600;
}

.input-wrapper input {
  width: 100%;
  padding: 14px 16px;
  border: 2px solid #e1e5e8;
  border-radius: 12px;
  font-size: 1rem;
  color: #333;
  background: #f8fafc;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.input-wrapper input:focus {
  outline: none;
  border-color: #42b983;
  background: #ffffff;
  box-shadow: 0 0 0 4px rgba(66, 185, 131, 0.1);
}

.input-wrapper input.has-error {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ff4d4f;
  font-size: 0.9rem;
  background: #fff2f0;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #ffccc7;
}

.submit-btn {
  margin-top: 10px;
  width: 100%;
  padding: 14px;
  background: #42b983;
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 54px;
}

.submit-btn:hover:not(:disabled) {
  background: #36a372;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(66, 185, 131, 0.25);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  background: #a0d8b8;
  cursor: not-allowed;
}

.toggle-mode {
  text-align: center;
  font-size: 0.95rem;
  color: #666;
  margin-top: -8px;
}

.toggle-mode a {
  color: #42b983;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.3s;
}

.toggle-mode a:hover {
  color: #2c8c61;
  text-decoration: underline;
}

/* Loading 动画 */
.loader {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #ffffff;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 注册成功罩层样式 */
.success-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(5px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.success-card {
  background: #fff;
  padding: 40px;
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  text-align: center;
  max-width: 400px;
  width: 90%;
  animation: slideUp 0.4s ease cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes slideUp {
  from { transform: translateY(30px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.success-icon {
  width: 80px;
  height: 80px;
  background: #e6f6ef;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.success-card h2 {
  color: #1a1a1a;
  font-size: 1.8rem;
  margin: 0 0 10px 0;
}

.success-card p {
  color: #666;
  margin: 0 0 30px 0;
  line-height: 1.5;
}

.success-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.enter-btn {
  width: 100%;
  padding: 14px;
  background: #42b983;
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.enter-btn:hover {
  background: #36a372;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(66, 185, 131, 0.25);
}

.back-btn {
  width: 100%;
  padding: 14px;
  background: transparent;
  color: #666;
  border: 1px solid #ddd;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.back-btn:hover {
  background: #f5f5f5;
  color: #333;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-card {
    flex-direction: column;
    min-height: auto;
  }
  
  .login-left {
    padding: 40px 30px;
  }
  
  .brand-content h1 {
    font-size: 2rem;
  }
  
  .features {
    display: none;
  }
  
  .login-right {
    padding: 40px 30px;
  }
}
</style>
