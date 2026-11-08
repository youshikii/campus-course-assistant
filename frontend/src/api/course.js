import request from '@/utils/request'

const base = '/api/admin/courses'
export const getCourseList = (params) => request.get(base, { params })
export const getCourseDetail = (id) => request.get(`${base}/${id}`)
export const createCourse = (data) => request.post(base, data)
export const updateCourse = (id, data) => request.put(`${base}/${id}`, data)
export const deleteCourse = (id) => request.delete(`${base}/${id}`)
