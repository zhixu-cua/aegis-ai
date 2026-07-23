<template>
  <div class="login-container">
    <h2>Login</h2>
    <form @submit.prevent="handleLogin">
      <div class="form-group">
        <label for="username">Username</label>
        <input type="text" id="username" v-model="username" required />
      </div>
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" v-model="password" required />
      </div>
      <button type="submit">Login</button>
      <p v-if="error" class="error-msg">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import request from '../api/request';

const username = ref('');
const password = ref('');
const error = ref('');
const router = useRouter();

const handleLogin = async () => {
  error.value = '';
  try {
    const res: any = await request.post('/user/doLogin', {
      username: username.value,
      password: password.value
    });
    
    // 假设后端返回的数据格式包含 token
    if (res.code === 200 && res.data && res.data.tokenValue) {
      localStorage.setItem('satoken', res.data.tokenValue);
      router.push('/chat');
    } else if (res.data && typeof res.data === 'string') {
      // 兼容直接返回 token 字符串
      localStorage.setItem('satoken', res.data);
      router.push('/chat');
    } else {
      error.value = res.msg || 'Login failed';
    }
  } catch (err: any) {
    error.value = err.message || 'Error occurred during login';
  }
};
</script>

<style scoped>
.login-container {
  max-width: 400px;
  margin: 100px auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  text-align: center;
}
.form-group {
  margin-bottom: 15px;
  text-align: left;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
}
.form-group input {
  width: 100%;
  padding: 8px;
  box-sizing: border-box;
}
button {
  width: 100%;
  padding: 10px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.error-msg {
  color: red;
  margin-top: 10px;
}
</style>
