import { useEffect, useMemo, useState } from 'react'
import './App.css'

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value || 0)
const pct = value => `${value >= 0 ? '+' : ''}${Number(value || 0).toFixed(2)}%`
const periods = [['annual', 'Annual P&L'], ['monthly', 'Monthly P&L'], ['weekly', 'Weekly P&L'], ['daily', 'Today’s P&L']]

async function getJson(url) {
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json()
}

async function openFyersAuthentication(setStatus = () => {}) {
  const loginWindow = window.open('about:blank', 'fyers-oauth')
  try {
    const response = await fetch('/api/auth/start', { cache: 'no-store' })
    const data = await response.json()
    if (!response.ok || !data.url) throw new Error(data.error || 'Could not start Fyers authentication')
    if (loginWindow) {
      loginWindow.opener = null
      loginWindow.location.replace(data.url)
    } else {
      window.location.assign(data.url)
    }
    setStatus('Complete login and 2FA in the browser')
  } catch (error) {
    if (loginWindow) loginWindow.close()
    setStatus(error.message)
  }
}

function Metric({ label, value, green, negative }) {
  return <article className="metric"><small>{label}</small><strong className={green ? 'positive' : negative ? 'negative' : ''}>{value}</strong></article>
}

function SectorDetails({ sector }) {
  if (!sector) return <section className="drivers-panel" aria-live="polite"><div className="panel-title"><div><p className="eyebrow">SELECT A SECTOR</p><h2>Constituent stocks appear here</h2></div></div><div className="empty">Choose a sector to inspect its current constituent data.</div></section>
  const drivers = sector.drivers || []
  return <section className="drivers-panel" aria-live="polite"><div className="panel-title"><div><p className="eyebrow">{sector.name.toUpperCase()}</p><h2>Constituent stocks</h2></div><span>{sector.change == null ? 'Move unavailable' : pct(sector.change)}</span></div>{drivers.length ? <div className="table"><div className="row heading"><span>Stock</span><span>Contribution</span><span>Move</span><span>Price</span></div>{drivers.map(driver => <div className="row" key={driver.ticker}><b>{driver.ticker}</b><span className={driver.contribution == null ? '' : driver.contribution >= 0 ? 'positive' : 'negative'}>{driver.contribution == null ? '—' : `${driver.contribution >= 0 ? '+' : ''}${Number(driver.contribution).toFixed(3)}`}</span><span className={driver.change == null ? '' : driver.change >= 0 ? 'positive' : 'negative'}>{driver.change == null ? '—' : pct(driver.change)}</span><span>{driver.price == null ? '—' : money(driver.price)}</span></div>)}</div> : <div className="empty">No constituents are configured for this sector.</div>}</section>
}

export default function App() {
  const [tab, setTab] = useState('sectors')
  const [heatmap, setHeatmap] = useState({ sectors: [] })
  const [heatmapState, setHeatmapState] = useState({ loading: true, error: '' })
  const [selectedName, setSelectedName] = useState('')
  const [account, setAccount] = useState({ positions: [] })
  const [period, setPeriod] = useState('daily')
  const [report, setReport] = useState({ records: [], summary: {} })
  const [authStatus, setAuthStatus] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setHeatmap(await getJson('/api/heatmap'))
        setHeatmapState({ loading: false, error: '' })
      } catch (error) {
        setHeatmapState({ loading: false, error: error.message || 'Sector data is unavailable.' })
      }
    }
    load()
    const id = setInterval(load, 30 * 60 * 1000)
    return () => clearInterval(id)
  }, [])
  useEffect(() => { const load = () => getJson('/api/account').then(setAccount).catch(() => {}); load(); const id = setInterval(load, 10000); return () => clearInterval(id) }, [])
  useEffect(() => { getJson(`/api/realized-pnl?period=${period}`).then(setReport).catch(() => {}) }, [period])

  const sectors = useMemo(() => [...(heatmap.sectors || [])].sort((a, b) => (b.change ?? -Infinity) - (a.change ?? -Infinity)), [heatmap.sectors])
  const selected = sectors.find(sector => sector.name === selectedName)
  const open = (account.positions || []).filter(position => Number(position.netQty ?? position.net_qty ?? 0) !== 0)

  return <main className="terminal"><aside className="sidebar"><div className="brand"><span>◈</span><div><b>Sector Pulse</b><small>Trading workspace</small></div></div><nav><button className={tab === 'sectors' ? 'active' : ''} onClick={() => setTab('sectors')}>Sector-led analysis</button><button className={tab === 'broker' ? 'active' : ''} onClick={() => setTab('broker')}>Live feed & positions <em>{open.length}</em></button></nav><div className="broker"><small>BROKER CONNECTION</small><strong><i className={account.connected ? 'online' : ''}></i>{account.connected ? 'Fyers connected' : 'Fyers unavailable'}</strong><button onClick={() => openFyersAuthentication(setAuthStatus)}>Refresh authentication</button>{authStatus && <small>{authStatus}</small>}</div></aside><section className="workspace">{tab === 'sectors' ? <><header><div><p className="eyebrow">SECTOR-LED ANALYSIS</p><h1>Leadership map</h1></div><div className="market-status"><i className={heatmap.connected ? 'online' : ''}></i>{heatmap.connected ? 'Live Fyers feed' : 'Feed unavailable'}</div></header><section className="heatmap-panel"><div className="panel-title"><div><p className="eyebrow">SECTOR STRENGTH</p><h2>Choose a sector to inspect its stocks</h2></div><span>Refreshes every 30 minutes</span></div>{heatmapState.loading ? <div className="empty" role="status">Loading sectors…</div> : heatmapState.error ? <div className="empty error" role="alert">{heatmapState.error}</div> : sectors.length ? <div className="sector-grid" aria-label="Sector heat map">{sectors.map(sector => <button type="button" className={`sector ${sector.change == null ? 'unavailable' : sector.change >= 0 ? 'gain' : 'loss'} ${selectedName === sector.name ? 'selected' : ''}`} aria-pressed={selectedName === sector.name} onClick={() => setSelectedName(sector.name)} key={sector.name}><b>{sector.name}</b><small>{sector.index}</small><strong>{sector.change == null ? '—' : pct(sector.change)}</strong><span>{sector.weight}% weight · View stocks</span></button>)}</div> : <div className="empty">No sectors are available yet.</div>}</section><SectorDetails sector={selected} /></> : <><header><div><p className="eyebrow">LIVE FEED & POSITIONS</p><h1>Broker dashboard</h1></div><div className="market-status">Updates every 10 seconds</div></header><section className="metrics"><Metric label="Live P&L" value={money(account.pnl)} green={Number(account.pnl) >= 0} negative={Number(account.pnl) < 0}/><Metric label="Open positions" value={open.length}/><Metric label="Available funds" value={money(account.available_funds)}/><Metric label="Closed P&L" value={money(report.summary?.net_pnl)} green={Number(report.summary?.net_pnl) >= 0} negative={Number(report.summary?.net_pnl) < 0}/></section><section className="content"><section className="heatmap-panel"><div className="panel-title"><h2>Open positions</h2></div><div className="table">{open.length ? open.map((position, index) => <div className="row" key={index}><b>{position.symbol || position.symbol_name}</b><span>Qty {position.netQty ?? position.net_qty}</span><span>Avg {money(position.netAvg ?? position.net_avg)}</span><strong className={(position.pl ?? 0) >= 0 ? 'positive' : 'negative'}>{money(position.pl)}</strong></div>) : <div className="empty">No open positions.</div>}</div></section><section className="ticket"><div className="panel-title"><h2>Closed positions</h2></div><div className="pnl-nav">{periods.map(([id, label]) => <button key={id} className={period === id ? 'active' : ''} onClick={() => setPeriod(id)}>{label}</button>)}</div><div className="pnl-table">{report.records?.length ? report.records.map((record, index) => <div className="pnl-row" key={index}><b>{record.symbol}</b><span>{record.buy_qty} / {record.sell_qty}</span><strong className={record.pnl >= 0 ? 'positive' : 'negative'}>{money(record.pnl)}</strong></div>) : <div className="empty">No closed positions for this period.</div>}</div></section></section></>}</section></main>
}
