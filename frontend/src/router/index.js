import { getToken, getUserInfo } from '@/utils/auth'
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/manager/home' },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layout.vue'),
      children: [
        { path: 'home', name: 'Home', component: () => import('@/views/Home.vue') },
        { path: 'assistant', name: 'Assistant', component: () => import('@/views/Assistant.vue') },
        {
          path: 'course-assistant',
          name: 'CourseAssistant',
          component: () => import('@/views/CourseAssistant.vue')
        },
        { path: 'courses', name: 'Courses', component: () => import('@/views/Courses.vue') },
        {
          path: 'my-schedules',
          name: 'MySchedules',
          component: () => import('@/views/MySchedules.vue')
        },
        {
          path: 'schedule-management',
          name: 'ScheduleManagement',
          component: () => import('@/views/ScheduleManagement.vue'),
          meta: { admin: true }
        },
        {
          path: 'course-management',
          name: 'CourseManagement',
          component: () => import('@/views/CourseManagement.vue'),
          meta: { admin: true }
        },
        { path: 'documents', name: 'Documents', component: () => import('@/views/Documents.vue') },
        {
          path: 'kb-documents',
          name: 'KBDocuments',
          component: () => import('@/views/KBDocuments.vue'),
          meta: { admin: true }
        },
        { path: 'plans', name: 'Plans', component: () => import('@/views/Plans.vue') },
        { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') },
        { path: 'password', name: 'Password', component: () => import('@/views/Password.vue') },
        {
          path: 'user',
          name: 'User',
          component: () => import('@/views/User.vue'),
          meta: { admin: true }
        }
      ]
    },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') }
  ]
})

// 路由守卫：验证token
router.beforeEach((to, from) => {
  const token = getToken()

  if (to.path === '/login' || to.path === '/register') {
    return true
  } else {
    if (token && to.meta.admin && getUserInfo()?.role !== 'admin') return '/manager/home'
    return token ? true : '/login'
  }
})

export default router
