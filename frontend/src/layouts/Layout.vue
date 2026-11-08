<template>
  <el-container class="app-frame">
    <el-aside class="app-sidebar">
      <div class="sidebar-header">
        <router-link class="brand" to="/manager/home">
          <span class="brand-icon"><el-icon><Reading /></el-icon></span>
          <span>校园课程助手</span>
        </router-link>
        <button
          class="mobile-menu"
          type="button"
          aria-controls="campus-navigation"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          <el-icon><Menu /></el-icon>
          菜单
        </button>
      </div>
      <nav id="campus-navigation" :class="{ 'is-open': menuOpen }" aria-label="功能导航">
        <el-menu router :default-active="route.path" class="main-menu">
          <el-menu-item-group title="学习空间">
            <el-menu-item v-for="item in learningLinks" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group v-if="userInfo?.role === 'admin'" title="教学管理">
            <el-menu-item v-for="item in adminLinks" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-menu-item>
          </el-menu-item-group>
        </el-menu>
      </nav>
    </el-aside>
    <el-container class="workspace">
      <el-header class="app-header">
        <div class="breadcrumb">
          <span>{{ isManagementPage ? '教学管理' : '学习空间' }}</span>
          <span aria-hidden="true">/</span>
          <strong>{{ titles[route.name] || '个人设置' }}</strong>
        </div>
        <el-dropdown @command="handleCommand">
          <button class="account-menu" type="button" aria-label="账户菜单">
            <el-avatar :size="28" :src="userInfo?.avatar || ''">{{
              userInfo?.name?.slice(0, 1) || '同'
            }}</el-avatar>
            <span>{{ userInfo?.name }}</span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人信息</el-dropdown-item>
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="workspace-main"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { logout } from '@/utils/auth'
import { useUser } from '@/utils/user'
import {
  ArrowDown, Calendar, ChatDotRound, FolderOpened, House, List, Menu, Reading, User
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { userInfo } = useUser()
const menuOpen = ref(false)
const learningLinks = [
  { label: '学习概览', path: '/manager/home', icon: House },
  { label: '我的课表', path: '/manager/my-schedules', icon: Calendar },
  { label: '学习计划', path: '/manager/plans', icon: List },
  { label: '智能助手', path: '/manager/assistant', icon: ChatDotRound },
  { label: '课程助手', path: '/manager/course-assistant', icon: ChatDotRound },
  { label: '我的课程', path: '/manager/courses', icon: Reading },
  { label: '课程资料库', path: '/manager/documents', icon: FolderOpened }
]
const adminLinks = [
  { label: '课表管理', path: '/manager/schedule-management', icon: Calendar },
  { label: '课程管理', path: '/manager/course-management', icon: Reading },
  { label: '课程资料管理', path: '/manager/kb-documents', icon: FolderOpened },
  { label: '用户管理', path: '/manager/user', icon: User }
]
const titles = {
  Home: '学习概览',
  Assistant: '智能助手',
  CourseAssistant: '课程助手',
  Courses: '我的课程',
  CourseManagement: '课程管理',
  MySchedules: '我的课表',
  ScheduleManagement: '课表管理',
  Documents: '课程资料库',
  KBDocuments: '课程资料管理',
  Plans: '学习计划',
  User: '用户管理',
  Profile: '个人信息',
  Password: '修改密码'
}
const isManagementPage = computed(() => adminLinks.some((item) => item.path === route.path))
watch(() => route.path, () => { menuOpen.value = false })

function handleCommand(command) {
  if (command === 'logout') {
    logout()
    router.push('/login')
  } else router.push(`/manager/${command}`)
}
</script>

<style scoped>
.app-frame { min-height: 100vh; --sidebar-width: 216px; }
.app-sidebar {
  width: var(--sidebar-width);
  position: fixed;
  inset: 0 auto 0 0;
  overflow-y: auto;
  background: var(--campus-surface);
  border-right: 1px solid var(--campus-line);
}
.sidebar-header { padding: 18px 14px 12px; }
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--campus-ink);
  font-size: 15px;
  font-weight: 680;
}
.brand-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 9px;
  background: var(--campus-ink);
  color: white;
  font-size: 17px;
}
.main-menu { border: 0; padding: 0 9px 12px; }
.main-menu :deep(.el-menu-item-group__title) {
  padding: 13px 9px 6px !important;
  font-size: 12px;
  color: var(--campus-muted);
}
.main-menu .el-menu-item {
  height: 38px;
  line-height: 38px;
  margin: 2px 0;
  padding-inline: 9px !important;
  border-radius: 8px;
  color: var(--campus-text);
}
.main-menu .el-menu-item.is-active {
  color: var(--campus-accent);
  background: var(--campus-accent-soft);
  font-weight: 650;
}
.main-menu .el-menu-item .el-icon { font-size: 16px; margin-right: 9px; }
.mobile-menu { display: none; }
.workspace { margin-left: var(--sidebar-width); min-width: 0; }
.app-header {
  height: 55px;
  border-bottom: 1px solid var(--campus-line);
  background: var(--campus-surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-inline: clamp(14px, 3.2vw, 36px);
}
.breadcrumb { display: flex; align-items: center; gap: 9px; font-size: 13px; color: var(--campus-muted); }
.breadcrumb strong { color: var(--campus-ink); font-weight: 650; }
.account-menu {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 8px;
  padding: 4px 5px;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: var(--campus-text);
}
.account-menu:hover { background: var(--campus-canvas); }
.account-menu span:not(.el-avatar) { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.workspace-main { padding: clamp(16px, 3.2vw, 36px); }
@media (max-width: 850px) { .app-frame { --sidebar-width: 174px; } }
@media (max-width: 680px) {
  .app-frame { flex-direction: column; }
  .app-sidebar { position: static; width: 100%; border-right: 0; border-bottom: 1px solid var(--campus-line); }
  .sidebar-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 14px; }
  .mobile-menu { display: inline-flex; align-items: center; gap: 5px; padding: 7px 10px; border: 1px solid var(--campus-line); border-radius: 8px; background: var(--campus-surface); color: var(--campus-ink); font: inherit; cursor: pointer; }
  #campus-navigation:not(.is-open) { display: none; }
  .workspace { margin-left: 0; }
  .app-header { height: 46px; }
  .workspace-main { padding: 16px 14px; }
}
</style>
