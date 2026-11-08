import request from '@/utils/request'

const base = '/api/study-plans'
export const getStudyPlans = (params) => request.get(base, { params })
export const saveStudyPlan = (data) => request.post(base, data)
export const deleteStudyPlan = (id) => request.delete(`${base}/${id}`)
export const updateStudyPlanStatus = (id, status) => request.patch(`${base}/${id}`, { status })
