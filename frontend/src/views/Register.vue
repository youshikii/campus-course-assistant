<template>
  <div class="auth-screen">
    <div class="auth-card">
      <header class="auth-heading">
        <span class="auth-product">校园课程助手</span>
        <h1>创建学生账号</h1>
        <p>注册后即可查看课表并安排学习计划。</p>
      </header>

      <el-form ref="formRef" :rules="rules" :model="form" label-width="0px" style="width: 100%">
        <el-form-item prop="username">
          <el-input
            size="large"
            v-model="form.username"
            placeholder="请输入账号"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            type="password"
            size="large"
            v-model="form.password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item prop="confirmPassword">
          <el-input
            type="password"
            size="large"
            v-model="form.confirmPassword"
            placeholder="请确认密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <div>
          <el-button
            size="large"
            type="primary"
            :loading="loadingValue"
            style="width: 100%"
            @click="register"
            >注 册</el-button
          >
          <div style="text-align: right; margin-top: 20px">
            已有账号？请
            <router-link style="color: var(--el-color-primary)" to="/login">登录</router-link>
          </div>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { registerApi } from '@/api/auth'
import router from '@/router'

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const loadingValue = ref(false)

const formRef = ref()

const validatePass = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请确认密码'))
  } else {
    if (value !== form.password) {
      callback(new Error('两次密码输入不一致'))
    } else {
      callback()
    }
  }
}
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirmPassword: [{ validator: validatePass, trigger: 'blur' }]
}

const register = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loadingValue.value = true
  try {
    const res = await registerApi(form)
    if (res.code === 200) {
      ElMessage.success('注册成功')
      await router.push('/login')
    }
  } finally {
    loadingValue.value = false
  }
}
</script>
