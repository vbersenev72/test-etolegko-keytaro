import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

export const fetchMeta = () => api.get('/meta').then(r => r.data)
export const fetchCampaigns = () => api.get('/campaigns').then(r => r.data)
export const createCampaign = (data) => api.post('/campaigns', data).then(r => r.data)
export const fetchStreams = (id) => api.get(`/campaigns/${id}/streams`).then(r => r.data)
export const addOffer = (campaignId, streamId, offerId) =>
  api.post(`/campaigns/${campaignId}/streams/${streamId}/offers`, { offer_id: offerId }).then(r => r.data)
export const removeOffer = (campaignId, streamId, offerId) =>
  api.delete(`/campaigns/${campaignId}/streams/${streamId}/offers/${offerId}`).then(r => r.data)
