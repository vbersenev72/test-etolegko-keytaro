import { useEffect, useState } from 'react'
import {
  fetchMeta,
  fetchCampaigns,
  createCampaign,
  fetchStreams,
  addOffer,
  removeOffer,
} from './api.js'

const GEO_LIST = ['AU', 'US', 'DE', 'GB', 'ES', 'IT', 'FR', 'PL', 'BR', 'MX', 'PE', 'TH', 'ID', 'MY', 'IN']

export default function App() {
  const [meta, setMeta] = useState({ offers: [], domains: [], groups: [] })
  const [campaigns, setCampaigns] = useState([])
  const [error, setError] = useState('')

  // форма создаватора
  const [name, setName] = useState('')
  const [geo, setGeo] = useState('AU')
  const [offerId, setOfferId] = useState('')
  const [creating, setCreating] = useState(false)

  // редактор
  const [editing, setEditing] = useState(null) // {campaign, streams}
  const [newOfferId, setNewOfferId] = useState('')
  const [editorBusy, setEditorBusy] = useState(false)

  const load = async () => {
    try {
      const [m, list] = await Promise.all([fetchMeta(), fetchCampaigns()])
      setMeta(m)
      setCampaigns(list)
    } catch (e) {
      setError(errText(e))
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    if (!name.trim() || !offerId) {
      setError('Заполните название и выберите оффер')
      return
    }
    setCreating(true)
    try {
      const res = await createCampaign({ name: name.trim(), geo, offer_id: Number(offerId) })
      setName('')
      setOfferId('')
      await load()
      openEditor(res.campaign.id)
    } catch (e) {
      setError(errText(e))
    } finally {
      setCreating(false)
    }
  }

  const openEditor = async (id) => {
    setError('')
    try {
      const data = await fetchStreams(id)
      setEditing(data)
      setNewOfferId('')
    } catch (e) {
      setError(errText(e))
    }
  }

  const handleAdd = async () => {
    if (!newOfferId) return
    setEditorBusy(true); setError('')
    try {
      await addOffer(editing.campaign.id, offersStream().id, Number(newOfferId))
      const data = await fetchStreams(editing.campaign.id)
      setEditing(data); setNewOfferId('')
    } catch (e) { setError(errText(e)) } finally { setEditorBusy(false) }
  }

  const handleRemove = async (offerId) => {
    setEditorBusy(true); setError('')
    try {
      await removeOffer(editing.campaign.id, offersStream().id, offerId)
      const data = await fetchStreams(editing.campaign.id)
      setEditing(data)
    } catch (e) { setError(errText(e)) } finally { setEditorBusy(false) }
  }

  const offersStream = () => {
    const s = editing.streams.find(s => s.offers.length > 0)
    return s || editing.streams[editing.streams.length - 1]
  }

  const offerName = (id) => {
    const o = meta.offers.find(o => o.id === id)
    return o ? `#${o.id} ${o.name}` : `#${id}`
  }

  return (
    <div className="container">
      <h1>Обёртка над Keitaro</h1>
      {error && <div className="error">{error}</div>}

      <section className="card">
        <h2>Создаватор кампаний</h2>
        <form onSubmit={handleCreate} className="form">
          <label>
            Название кампании
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Например: Test campaign" />
          </label>
          <label>
            Гео
            <select value={geo} onChange={e => setGeo(e.target.value)}>
              {GEO_LIST.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </label>
          <label>
            Оффер
            <select value={offerId} onChange={e => setOfferId(e.target.value)}>
              <option value="">— выберите оффер —</option>
              {meta.offers.map(o => (
                <option key={o.id} value={o.id}>#{o.id} {o.name}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={creating}>{creating ? 'Создаю…' : 'Создать кампанию'}</button>
        </form>
        <p className="hint">
          Поток 1: все из {geo} → Google. Поток 2: выбранный оффер. Домен, группа и источник подставляются из Keitaro автоматически.
        </p>
      </section>

      <section className="card">
        <h2>Кампании</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Название</th><th>Группа</th><th>Домен</th><th>Статус</th><th></th></tr>
          </thead>
          <tbody>
            {campaigns.map(c => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td>{c.name}</td>
                <td>{c.group || '—'}</td>
                <td>{c.domain || '—'}</td>
                <td>{c.state}</td>
                <td>
                  <button onClick={() => openEditor(c.id)}>Редактировать</button>
                </td>
              </tr>
            ))}
            {campaigns.length === 0 && (
              <tr><td colSpan={6} className="empty">Пока нет кампаний</td></tr>
            )}
          </tbody>
        </table>
      </section>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Редактор: {editing.campaign.name}</h2>
              <button className="close" onClick={() => setEditing(null)}>×</button>
            </div>
            <div className="streams">
              {editing.streams.map(s => (
                <div key={s.id} className="stream">
                  <div className="stream-title">
                    <strong>{s.name}</strong>
                    <span className="tag">{s.schema}</span>
                  </div>
                  {s.action_payload && <div className="hint">URL: {s.action_payload}</div>}
                  {s.filters.length > 0 && (
                    <div className="hint">
                      Фильтры: {s.filters.map(f => `${f.name} ${f.mode} ${(f.payload || []).join(', ')}`).join('; ')}
                    </div>
                  )}
                  {s.offers.length > 0 && (
                    <table className="offers">
                      <thead><tr><th>Оффер</th><th>Доля</th><th></th></tr></thead>
                      <tbody>
                        {s.offers.map(o => (
                          <tr key={o.offer_id}>
                            <td>{offerName(o.offer_id)}</td>
                            <td>{o.share}%</td>
                            <td>
                              <button className="danger" disabled={editorBusy} onClick={() => handleRemove(o.offer_id)}>
                                Удалить
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {s === offersStream() && (
                    <div className="add-offer">
                      <select value={newOfferId} onChange={e => setNewOfferId(e.target.value)}>
                        <option value="">— выберите оффер —</option>
                        {meta.offers
                          .filter(o => !s.offers.some(x => x.offer_id === o.id))
                          .map(o => <option key={o.id} value={o.id}>#{o.id} {o.name}</option>)}
                      </select>
                      <button disabled={!newOfferId || editorBusy} onClick={handleAdd}>Добавить оффер</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <p className="hint">При добавлении/удалении офферов доли автоматически пересчитываются так, чтобы сумма была 100%.</p>
          </div>
        </div>
      )}
    </div>
  )
}

const errText = (e) =>
  e?.response?.data?.detail ? String(e.response.data.detail) : e?.message || 'Неизвестная ошибка'
