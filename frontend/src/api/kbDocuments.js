import request from '@/utils/request'

export const getKBDocuments = (params) => request.get('/api/admin/kb-documents', { params })
export const previewKBDocument = (id) => request.get(`/api/admin/kb-documents/${id}/preview`)
export const deleteKBDocument = (id) => request.delete(`/api/admin/kb-documents/${id}`)
export function uploadKBDocuments(files) {
  const data = new FormData()
  files.forEach((file) => data.append('files', file))
  return request.post('/api/admin/kb-documents/batch', data, { timeout: 180000 })
}
