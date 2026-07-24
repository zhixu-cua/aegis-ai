import axios, {type InternalAxiosRequestConfig, type AxiosResponse, AxiosError } from 'axios';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000,
});

// 请求拦截器
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 从 localStorage 中获取 token
    const token = localStorage.getItem('satoken');
    if (token) {
      // 注入 satoken 请求头
      config.headers.set('satoken', token);
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data;
  },
  (error: AxiosError) => {
    // 可以统一处理错误
    if (error.response && error.response.status === 401) {
      // token 过期或无效，跳转登录
      localStorage.removeItem('satoken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default request;
