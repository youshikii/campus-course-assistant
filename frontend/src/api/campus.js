import request from '@/utils/request'

export const getCourses = (params) => request.get('/api/courses', { params })
export const saveCourse = (id, data) =>
  id ? request.put(`/api/courses/${id}`, data) : request.post('/api/courses', data)
export const deleteCourse = (id) => request.delete(`/api/courses/${id}`)
export const getDocuments = () => request.get('/api/documents')
export const getDocument = (id) => request.get(`/api/documents/${id}`)
export const uploadDocument = (file, courseId) => {
  const data = new FormData()
  data.append('file', file)
  if (courseId) data.append('course_id', courseId)
  return request.post('/api/documents', data, { timeout: 180000 })
}
export const indexDocument = (id) =>
  request.post(`/api/documents/${id}/index`, {}, { timeout: 180000 })
export const deleteDocument = (id) => request.delete(`/api/documents/${id}`)
export const searchDocuments = (data) =>
  request.post('/api/documents/search', data, { timeout: 60000 })
export const getPlans = () => request.get('/api/plans')
export const createPlan = (data) => request.post('/api/plans', data)
export const setPlanStatus = (id, status) => request.patch(`/api/plans/${id}`, { status })
export const deletePlan = (id) => request.delete(`/api/plans/${id}`)
export const getChatConfig = () => request.get('/api/chat/config')
export const getSessions = () => request.get('/api/chat/sessions')
export const createSession = () => request.post('/api/chat/sessions')
export const getMessages = (id) => request.get(`/api/chat/sessions/${id}/messages`)
export const deleteSession = (id) => request.delete(`/api/chat/sessions/${id}`)
