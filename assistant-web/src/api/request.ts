import axios, {type InternalAxiosRequestConfig, type AxiosResponse, AxiosError } from 'axios';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000, // 增加到120秒，大模型推理时间较长
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
    const res = response.data;
    // 拦截业务自定义的 401 状态码 (NotLoginException 会返回这个)
    if (res && res.code === 401) {
      localStorage.removeItem('satoken');
      window.location.href = '/login';
      return Promise.reject(new Error(res.msg || '未登录/登录过期'));
    }
    return res;
  },
  (error: AxiosError) => {
    // 统一处理 HTTP 层面的 401 状态码
    if (error.response && error.response.status === 401) {
      // token 过期或无效，跳转登录
      localStorage.removeItem('satoken');
      window.location.href = '/login';
    }
    const errorMessage =
      (error.response?.data as { msg?: string; detail?: string } | undefined)?.msg ||
      (error.response?.data as { msg?: string; detail?: string } | undefined)?.detail ||
      error.message ||
      '请求失败';
    return Promise.reject(new Error(errorMessage));
  }
);

export default request;
