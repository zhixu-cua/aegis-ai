import { createRouter, createWebHistory, type RouteRecordRaw, type NavigationGuardNext, type RouteLocationNormalized } from 'vue-router';
import Login from '../views/Login.vue';
import Chat from '../views/Chat.vue';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: Chat,
    meta: { requiresAuth: true }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// 全局路由守卫
router.beforeEach((to: RouteLocationNormalized, _from: RouteLocationNormalized, next: NavigationGuardNext) => {
  const token = localStorage.getItem('satoken');
  
  if (to.meta.requiresAuth && !token) {
    // 如果页面需要鉴权且未登录，重定向到登录页
    next('/login');
  } else if (to.path === '/login' && token) {
    // 如果已经登录却访问登录页，重定向到聊天页
    next('/chat');
  } else {
    next();
  }
});

export default router;
