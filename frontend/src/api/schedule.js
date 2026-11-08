import request from '@/utils/request'

const base = '/api/admin/schedules'
export const getMySchedules = (params) => request.get('/api/schedules/me', { params })
export const getScheduleList = (params) => request.get(base, { params })
export const getScheduleDetail = (id) => request.get(`${base}/${id}`)
export const createSchedule = (data) => request.post(base, data)
export const updateSchedule = (id, data) => request.put(`${base}/${id}`, data)
export const deleteSchedule = (id) => request.delete(`${base}/${id}`)
export const getStudentOptions = (keywords = '') =>
  request.get(`${base}/student-options`, { params: { keywords } })
