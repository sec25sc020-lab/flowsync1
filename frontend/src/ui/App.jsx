import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, Ambulance, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Camera,
  CarFront, Check, ChevronDown, ChevronRight, CircleHelp, Clock3, Download, Gauge, GitBranch,
  Layers3, LayoutDashboard, LogOut, MapPinned, Menu, Play, Radio, RefreshCw, Settings, Shield,
  ShieldCheck, Siren, SlidersHorizontal, TrafficCone, Upload, Users, X,
} from 'lucide-react';
import {
  Area, AreaChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { getJson, postJson, request } from './api.js';

const nav = [
  ['Overview', 'Dashboard', LayoutDashboard],
  ['OPERATIONS', 'Live traffic', Radio],
  ['', 'Signal control', TrafficCone],
  ['', 'Emergency corridor', Siren],
  ['INTELLIGENCE', 'Analytics', BarChart3],
  ['ADMINISTRATION', 'Settings', Settings],
];
const routes = {
  Dashboard: 'dashboard', 'Live traffic': 'live', 'Signal control': 'signals',
  'Emergency corridor': 'emergency', Analytics: 'analytics', Settings: 'settings',
};
const fmt = (value) => new Intl.NumberFormat('en-US').format(value ?? 0);
const shortTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

function App() {
  const [page, setPage] = useState('Dashboard');
  const [data, setData] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [settings, setSettings] = useState(null);
  const [audit, setAudit] = useState([]);
  const [managedIntersections, setManagedIntersections] = useState([]);
  const [identity, setIdentity] = useState(() => {
    try { return JSON.parse(localStorage.getItem('flowsync_identity')); } catch { return null; }
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [dashboard, chart, config] = await Promise.all([getJson('/dashboard'), getJson('/analytics'), getJson('/settings')]);
      setData(dashboard);
      setAnalytics(chart);
      setSettings(config);
      setError('');
    } catch (err) { setError(err.message); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const navigate = (event) => setPage(event.detail);
    window.addEventListener('flowsync-navigate', navigate);
    return () => window.removeEventListener('flowsync-navigate', navigate);
  }, []);
  useEffect(() => {
    if (!live) return undefined;
    const id = setInterval(async () => {
      try {
        const dashboard = await postJson('/simulation/tick', {});
        setData(dashboard);
        setError('');
      } catch (err) { setError(err.message); }
    }, 4000);
    return () => clearInterval(id);
  }, [live]);
  useEffect(() => {
    if (page === 'Settings' && identity?.role === 'admin') {
      Promise.all([getJson('/audit'), getJson('/admin/intersections')])
        .then(([entries, intersections]) => { setAudit(entries); setManagedIntersections(intersections); })
        .catch((err) => setError(err.message));
    }
  }, [page, identity]);

  async function action(fn, message) {
    setBusy(true);
    setError('');
    try { await fn(); await refresh(); if (message) setNotice(message); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  function signOut() {
    localStorage.removeItem('flowsync_token');
    localStorage.removeItem('flowsync_identity');
    setIdentity(null);
  }

  const title = page === 'Dashboard' ? 'Mobility overview' : page;
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#" onClick={(event) => event.preventDefault()}>
          <div className="brand-mark"><Activity size={21} strokeWidth={2.3} /></div>
          <span>flow<span className="brand-accent">sync</span><small>URBAN MOBILITY INTELLIGENCE</small></span>
        </a>
        <div className="workspace-switch"><div className="city-icon"><MapPinned size={16} /></div><span><b>Metro City</b><small>Operations center</small></span><ChevronDown size={15} /></div>
        <div className="nav-list">{nav.map(([section, label, Icon]) => <React.Fragment key={label}>
          {section && <div className="nav-section">{section}</div>}
          <button className={`nav-item ${page === label ? 'active' : ''}`} onClick={() => { setPage(label); setMobileOpen(false); }}>
            <Icon size={17} /><span>{label}</span>{label === 'Emergency corridor' && data?.emergency && <i className="nav-alert" />}
          </button>
        </React.Fragment>)}</div>
        <div className="sidebar-bottom">
          <div className="side-health"><span className="health-dot" /><span><b>All systems operational</b><small>Last checked just now</small></span></div>
          <div className="profile"><div className="avatar">{identity?.username?.[0]?.toUpperCase() || 'O'}</div><span><b>{identity?.username || 'City operator'}</b><small>{identity?.role || 'Demo access'}</small></span>
            {identity ? <button className="icon-button" title="Sign out" onClick={signOut}><LogOut size={16} /></button> : <button className="icon-button" title="Sign in" onClick={() => setPage('Settings')}><Shield size={16} /></button>}
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><button className="mobile-menu icon-button" onClick={() => setMobileOpen(!mobileOpen)}><Menu size={19} /></button><span>Metro City</span><ChevronRight size={14} /><b>{title}</b></div>
          <div className="topbar-right"><span className="simulation-pill"><span />SIMULATION MODE</span><span className="top-divider" /><span className="date-label">{new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
            <button className="notification-button" title="Refresh dashboard" onClick={refresh}><RefreshCw size={17} />{error && <i />}</button>
            <div className="avatar avatar-small">{identity?.username?.[0]?.toUpperCase() || 'O'}</div>
          </div>
        </header>
        <section className="page-wrap">
          <div className="page-heading"><div><div className="eyebrow"><span className="live-dot" />SYSTEM LIVE <span className="eyebrow-sep">/</span> {data?.updated_at ? shortTime(data.updated_at) : 'CONNECTING'}</div><h1>{title}</h1><p>{pageDescription(page)}</p></div>
            <div className="heading-actions"><button className={`button button-quiet ${live ? 'is-running' : ''}`} onClick={() => setLive(!live)}>{live ? <><span className="tiny-pulse" /> Live updates</> : <><Play size={15} /> Resume updates</>}</button>
              <button className="button button-primary" disabled={busy} onClick={() => action(() => postJson('/simulation/tick', {}).then(setData), 'Simulation advanced one tick.')}><Play size={15} fill="currentColor" /> Run simulation</button></div>
          </div>
          {error && <div className="alert error-alert"><AlertTriangle size={17} /><span><b>Connection or action error:</b> {error}<small>Start the FastAPI service to connect to the simulation.</small></span><button onClick={() => setError('')}><X size={16} /></button></div>}
          {notice && <div className="alert success-alert"><Check size={17} /><span>{notice}</span><button onClick={() => setNotice('')}><X size={16} /></button></div>}
          {!data ? <Loading /> : <PageContent page={page} data={data} analytics={analytics} settings={settings} setSettings={setSettings} audit={audit} managedIntersections={managedIntersections} setManagedIntersections={setManagedIntersections} identity={identity} setIdentity={setIdentity} action={action} busy={busy} refresh={refresh} />}
          <footer><span><span className="live-dot" />Simulation running</span><span>FlowSync Urban Mobility Platform <b>·</b> v0.1.0</span></footer>
        </section>
      </main>
    </div>
  );
}

function pageDescription(page) {
  return ({
    Dashboard: 'A real-time view of your city’s traffic network and signal performance.',
    'Live traffic': 'Monitor simulated traffic flow, approach queues, and uploaded media detections.',
    'Signal control': 'Manage intersection phases with transparent, adaptive signal timing.',
    'Emergency corridor': 'Coordinate a safe, verified emergency green corridor across intersections.',
    Analytics: 'Understand mobility patterns and compare adaptive and fixed-time strategies.',
    Settings: 'Configure signal policy, access controls, and review operator activity.',
  })[page];
}

function PageContent(props) {
  const { page, data } = props;
  if (page === 'Live traffic') return <LivePage {...props} />;
  if (page === 'Signal control') return <SignalPage {...props} />;
  if (page === 'Emergency corridor') return <EmergencyPage {...props} />;
  if (page === 'Analytics') return <AnalyticsPage {...props} />;
  if (page === 'Settings') return <SettingsPage {...props} managedIntersections={props.managedIntersections} setManagedIntersections={props.setManagedIntersections} />;
  return <DashboardPage {...props} />;
}

function MetricCard({ label, value, suffix, icon: Icon, tone, delta, detail }) {
  return <article className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={18} /></div><div className="metric-label">{label}</div><div className="metric-value">{value}<small>{suffix}</small></div>
    <div className="metric-footer">{delta ? <span className={`delta ${delta.startsWith('+') ? 'positive' : ''}`}><ArrowDownRight size={13} />{delta}</span> : <span className="metric-caption">{detail}</span>}{delta && <span className="metric-caption">{detail}</span>}</div>
  </article>;
}

function DashboardPage({ data, analytics }) {
  const metrics = data.metrics;
  const chartData = analytics?.hourly?.length ? analytics.hourly : [];
  const strongest = Math.max(...data.intersections.flatMap((x) => x.roads.map((road) => road.queue_length)), 1);
  return <>
    <div className="metrics-grid">
      <MetricCard label="Vehicles detected" value={fmt(metrics.total_vehicles)} icon={CarFront} tone="blue" delta="+8.2%" detail="vs previous hour" />
      <MetricCard label="Avg. waiting time" value={fmt(metrics.average_wait_seconds)} suffix="sec" icon={Clock3} tone="violet" delta="-12.4%" detail="vs previous hour" />
      <MetricCard label="Estimated queue" value={fmt(metrics.estimated_queue_length)} suffix="vehicles" icon={GitBranch} tone="amber" detail="across active intersections" />
      <MetricCard label="Active emergencies" value={fmt(metrics.active_emergencies)} icon={Siren} tone="mint" detail={data.emergency ? 'Corridor coordination active' : 'No active requests'} />
    </div>
    <div className="content-grid overview-grid">
      <section className="panel traffic-panel"><PanelHeader title="City traffic flow" tag="SIMULATED DATA" right={<span className="legend"><i className="legend-cyan" />Vehicles <i className="legend-blue" />Avg. wait</span>} />
        {chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}><defs><linearGradient id="trafficFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#30c7d9" stopOpacity=".22" /><stop offset="95%" stopColor="#30c7d9" stopOpacity="0" /></linearGradient></defs><CartesianGrid stroke="#202c3c" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="hour" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><YAxis yAxisId="left" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><Tooltip contentStyle={{ background: '#101d2d', border: '1px solid #27374a', borderRadius: 9, fontSize: 12 }} /><Area yAxisId="left" type="monotone" dataKey="vehicles" stroke="#34c6d6" strokeWidth={2.2} fill="url(#trafficFill)" /><Line yAxisId="right" type="monotone" dataKey="wait" stroke="#7b8dff" strokeWidth={2} dot={false} /></ComposedChart></ResponsiveContainer></div> : <EmptyChart />}
        <div className="chart-footnote"><span><i className="legend-cyan" />Vehicle count</span><span><i className="legend-blue" />Waiting time (sec)</span><span>36 stored samples · rolling 24h</span></div>
      </section>
      <section className="panel status-panel"><PanelHeader title="Network status" tag={`${data.intersections.length} INTERSECTIONS`} />
        <div className="intersection-list">{data.intersections.map((item) => {
          const peak = [...item.roads].sort((a, b) => b.queue_length - a.queue_length)[0];
          const score = Math.round(item.roads.reduce((sum, road) => sum + road.density, 0) / 4 * 100);
          return <div className="intersection-row" key={item.id}><div className={`junction-icon ${peak.congestion.toLowerCase()}`}><Layers3 size={16} /></div><div className="junction-info"><div><b>{item.name}</b><span className="junction-live"><i /> Active</span></div><small>{item.phase_direction} green · {item.remaining_seconds}s remaining</small><div className="mini-progress"><span style={{ width: `${score}%` }} /></div></div><div className="queue-stat"><b>{item.roads.reduce((sum, road) => sum + road.queue_length, 0)}</b><small>queue</small></div><span className={`badge ${peak.congestion.toLowerCase()}`}>{peak.congestion}</span></div>;
        })}</div>
        <button className="text-link" onClick={() => window.dispatchEvent(new CustomEvent('flowsync-navigate', { detail: 'Signal control' }))}>Manage intersections <ChevronRight size={14} /></button>
      </section>
    </div>
    <div className="content-grid bottom-grid">
      <section className="panel heat-panel"><PanelHeader title="Congestion map" tag="NETWORK HEATMAP" right={<span className="map-label"><MapPinned size={13} /> Metro City grid</span>} /><Heatmap intersections={data.intersections} peak={strongest} /></section>
      <section className="panel alerts-panel"><PanelHeader title="Traffic alerts" right={<button className="subtle-link" onClick={() => window.dispatchEvent(new CustomEvent('flowsync-navigate', { detail: 'Live traffic' }))}>View all</button>} />
        <div className="alert-list">{data.emergency && <AlertRow icon={Siren} color="red" label="Emergency corridor active" desc={`${data.emergency.vehicle_type} · ${data.emergency.origin} approach · ETA ${data.emergency.eta_seconds}s`} time="NOW" />}
          {data.alerts.slice(0, data.emergency ? 3 : 4).map((alert, index) => <AlertRow key={`${alert.intersection}-${alert.direction}-${index}`} icon={alert.level === 'Critical' ? AlertTriangle : Activity} color={alert.level === 'Critical' ? 'red' : 'amber'} label={`${alert.level} congestion detected`} desc={`${alert.intersection} · ${alert.direction} approach · queue of ${alert.queue}`} time="LIVE" />)}
          {!data.emergency && !data.alerts.length && <div className="empty-state">Traffic flow is moving smoothly.</div>}</div>
      </section>
    </div>
  </>;
}

function PanelHeader({ title, tag, right }) {
  return <div className="panel-header"><div><h2>{title}</h2>{tag && <span className="panel-tag">{tag}</span>}</div>{right}</div>;
}

function AlertRow({ icon: Icon, color, label, desc, time }) {
  return <div className="alert-row"><div className={`alert-icon ${color}`}><Icon size={15} /></div><div className="alert-copy"><b>{label}</b><small>{desc}</small></div><span className="alert-time">{time}</span></div>;
}

function Heatmap({ intersections, peak }) {
  const cells = intersections.flatMap((intersection) => intersection.roads.map((road) => ({ ...road, intersection: intersection.name })));
  return <div className="heatmap"><div className="map-grid" /><div className="map-road map-road-horizontal" /><div className="map-road map-road-vertical" />
    <div className="map-route route-a" /><div className="map-route route-b" />
    {intersections.map((intersection, index) => {
      const left = [27, 59, 79][index % 3]; const top = [51, 31, 65][index % 3];
      return <div className="map-intersection" key={intersection.id} style={{ left: `${left}%`, top: `${top}%` }}>
        <span className={`map-hotspot ${intersection.roads.some((r) => r.congestion === 'Critical') ? 'critical' : intersection.roads.some((r) => r.congestion === 'High') ? 'high' : ''}`} />
        <span className="map-pin"><TrafficCone size={13} /></span><span className="map-tooltip">{intersection.name}</span>
      </div>;
    })}
    <div className="map-legend"><b>Congestion</b><span><i className="legend-low" /> Low</span><span><i className="legend-medium" /> Medium</span><span><i className="legend-high" /> High</span><span><i className="legend-critical" /> Critical</span></div>
    <div className="map-caption">Queue intensity · {cells.length} approaches</div>
  </div>;
}

function SignalDiagram({ intersection, onOverride, readOnly = false }) {
  const [direction, setDirection] = useState(intersection.phase_direction);
  const [duration, setDuration] = useState(20);
  const positions = { North: 'north', East: 'east', South: 'south', West: 'west' };
  const roads = Object.fromEntries(intersection.roads.map((road) => [road.direction, road]));
  return <div className="intersection-diagram">
    <div className="diagram-grid-lines" />
    <div className="junction-center"><div className="center-dot"><TrafficCone size={18} /></div><span>{intersection.name}</span></div>
    {['North', 'East', 'South', 'West'].map((d) => <div className={`approach approach-${positions[d]}`} key={d}>
      <div className="approach-label"><span>{d}</span><b>{roads[d].queue_length} <small>queued</small></b></div>
      <div className="signal-head"><i className={roads[d].signal === 'red' ? 'red-lit' : ''} /><i className={roads[d].signal === 'yellow' ? 'yellow-lit' : ''} /><i className={roads[d].signal === 'green' ? 'green-lit' : ''} /></div>
      <div className="approach-stat"><span className={`tiny-status ${roads[d].congestion.toLowerCase()}`} />{roads[d].congestion} · {roads[d].waiting_seconds}s wait</div>
    </div>)}
    <div className="diagram-controller">{readOnly ? <><label>Current safe phase</label><small>{intersection.phase_direction} approach is {intersection.phase}; all conflicting approaches remain red.</small></> : <><label>Manual override direction</label><div className="controller-controls"><select value={direction} onChange={(e) => setDirection(e.target.value)}>{['North', 'East', 'South', 'West'].map((d) => <option key={d}>{d}</option>)}</select><input type="number" min="3" max="90" value={duration} onChange={(e) => setDuration(Number(e.target.value))} aria-label="Override duration in seconds" /><span>sec</span><button className="button button-primary" onClick={() => onOverride(intersection.id, direction, duration)}>Set green</button></div><small>All conflicting approaches remain red; a 3-second yellow clearance precedes the requested green.</small></>}</div>
  </div>;
}

function SignalPage({ data, action, busy }) {
  return <><div className="callout"><ShieldCheck size={18} /><span><b>Safe phase control enabled</b><small>One approach receives green at a time. Yellow clearance protects each phase transition.</small></span><span className="mode-chip">ADAPTIVE MODE</span></div>
    {data.intersections.map((intersection) => <section className="panel control-panel" key={intersection.id}><PanelHeader title={intersection.name} tag="4-WAY INTERSECTION" right={<span className={`badge ${intersection.phase === 'green' ? 'low' : 'amber'}`}>{intersection.phase_direction} {intersection.phase}</span>} />
      <SignalDiagram intersection={intersection} onOverride={(id, direction, duration) => action(() => postJson(`/signals/${id}/override`, { direction, duration_seconds: duration }), `Manual green set for ${direction} approach.`)} />
    </section>)}<p className="muted-note">Automatic allocation is bounded by configured minimum and maximum green times. Current mode uses a deterministic fairness-weighted queue and wait-time rule.</p>
  </>;
}

function EmergencyPage({ data, action, busy }) {
  const active = data.emergency;
  const [type, setType] = useState('Ambulance');
  const [origin, setOrigin] = useState('North');
  const [destination, setDestination] = useState('Market Street');
  return <><div className={`emergency-banner ${active ? 'emergency-active' : ''}`}><div className="emergency-big-icon"><Ambulance size={25} /></div><div><span className="eyebrow">PRIORITY RESPONSE NETWORK</span><h2>{active ? 'Corridor coordination in progress' : 'Emergency corridor standby'}</h2><p>{active ? `${active.vehicle_type} approaching from ${active.origin}. Intersection signal clearance is active.` : 'Request a simulated, verified emergency vehicle and FlowSync will safely clear the approach before giving priority green.'}</p></div><span className={`status-pill ${active ? 'status-red' : ''}`}><i />{active ? active.status.replace('-', ' ').toUpperCase() : 'STANDBY'}</span></div>
    <div className="emergency-grid"><section className="panel emergency-form"><PanelHeader title="Emergency request" tag="AUTHORIZED OPERATORS" /><div className="form-stack"><label>Emergency vehicle<select value={type} disabled={!!active} onChange={(e) => setType(e.target.value)}><option>Ambulance</option><option>Fire engine</option></select></label><label>Approaching direction<select value={origin} disabled={!!active} onChange={(e) => setOrigin(e.target.value)}>{['North', 'East', 'South', 'West'].map((d) => <option key={d}>{d}</option>)}</select></label><label>Destination intersection<select value={destination} disabled={!!active} onChange={(e) => setDestination(e.target.value)}>{['Central Square', 'River Bridge', 'Market Street'].map((d) => <option key={d}>{d}</option>)}</select></label>
      {active ? <button className="button button-danger" disabled={busy} onClick={() => action(() => postJson(`/emergencies/${active.id}/pass`, {}).then(() => {}), 'Emergency passed. Normal operation is being restored.')}><Check size={16} /> Confirm vehicle passed</button> : <button className="button button-danger" disabled={busy} onClick={() => action(() => postJson('/emergencies', { vehicle_type: type, origin, destination }), 'Emergency corridor requested and signals are clearing safely.')}><Siren size={16} /> Request green corridor</button>}
      <p className="form-hint"><ShieldCheck size={14} />The request is marked simulated and verified for this prototype. Existing active requests cannot be duplicated.</p></div></section>
      <section className="panel route-panel"><PanelHeader title="Corridor route" tag="CONNECTED NETWORK" /><div className="route-map"><div className="route-line" /><div className="route-node node-one"><span>1</span><small>Central Square</small></div><div className="route-node node-two"><span>2</span><small>River Bridge</small></div><div className="route-node node-three"><span>3</span><small>Market Street</small></div><div className="route-vehicle" style={{ left: active ? `${Math.max(14, 75 - active.eta_seconds * 4)}%` : '17%' }}><Ambulance size={18} /></div></div>
      <div className="route-facts"><div><small>VEHICLE STATUS</small><b>{active ? active.status.replace('-', ' ') : 'Awaiting request'}</b></div><div><small>ESTIMATED ARRIVAL</small><b>{active ? `${active.eta_seconds}s` : '—'}</b></div><div><small>GREEN CORRIDOR</small><b>{active ? active.origin : 'Inactive'}</b></div></div>
      <div className="safety-note"><ShieldCheck size={15} /><span><b>Safety interlock active</b><small>Conflicting directions stay red. A 3-second yellow clearance precedes emergency green.</small></span></div></section></div>
    <div className="callout subdued"><CircleHelp size={17} /><span><b>How this simulation works</b><small>Advance simulation ticks to move the response through approach, signal clearance, corridor green, and passed states. Normal signal scheduling resumes after passage.</small></span></div>
  </>;
}

function LivePage({ data }) {
  const [result, setResult] = useState(null);
  const [uploadError, setUploadError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState('');
  const [preview, setPreview] = useState('');
  const inputRef = React.useRef(null);
  async function upload(file) {
    if (!file) return;
    setUploadError(''); setResult(null); setPreview('');
    const accepted = ['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/quicktime', 'video/x-msvideo'];
    if (!accepted.includes(file.type) || file.size > 20 * 1024 * 1024) {
      setUploadError('Choose a JPG, PNG, WebP, MP4, AVI, or MOV file up to 20 MB.'); return;
    }
    setFileName(file.name);
    if (file.type.startsWith('image/')) setPreview(URL.createObjectURL(file));
    setUploading(true);
    try {
      const form = new FormData(); form.append('file', file);
      const response = await request('/detection/upload', { method: 'POST', body: form });
      setResult(await response.json());
    } catch (err) { setUploadError(err.message); }
    finally { setUploading(false); }
  }
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  return <><div className="live-summary"><div><span className="live-pulse" /><div><b>Simulation data stream</b><small>Sampled, clearly labelled traffic · updated {data.updated_at ? shortTime(data.updated_at) : '—'}</small></div></div><span className="simulation-pill"><span />SIMULATION</span></div>
    <div className="live-grid">{data.intersections.map((intersection) => <section className="panel live-intersection" key={intersection.id}><PanelHeader title={intersection.name} right={<span className="small-live"><i /> FEED SIMULATED</span>} /><SignalDiagram intersection={intersection} readOnly /><div className="stream-foot"><span><CarFront size={14} />{intersection.roads.reduce((sum, road) => sum + road.vehicle_count, 0)} vehicles</span><span><GitBranch size={14} />{intersection.roads.reduce((sum, road) => sum + road.queue_length, 0)} queued</span><span><Gauge size={14} />Peak: {intersection.roads.reduce((a, b) => a.queue_length > b.queue_length ? a : b).congestion}</span></div></section>)}</div>
    <section className="panel upload-panel"><PanelHeader title="Analyze traffic media" tag="OPTIONAL YOLO COMPUTER VISION" right={<span className="panel-tag">UPLOADS ARE PROCESSED LOCALLY</span>} />
      <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-msvideo" hidden onChange={(e) => upload(e.target.files?.[0])} />
      <button className="upload-zone" onClick={() => inputRef.current?.click()} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files?.[0]); }}><div className="upload-symbol"><Upload size={20} /></div><b>{uploading ? 'Analyzing media…' : 'Drop traffic media here, or browse files'}</b><span>JPG, PNG, WebP, MP4, AVI, MOV · Up to 20 MB</span><span className="button button-quiet"><Camera size={14} /> Choose media</span></button>
      <p className="upload-disclaimer"><Shield size={14} />Only local file upload is available. Camera feeds are not connected; configure a YOLO weights path to enable image/video detection.</p>
      {uploadError && <div className="alert error-alert"><AlertTriangle size={16} /><span>{uploadError}</span></div>}
      {uploading && <div className="upload-loading"><span className="spinner" />Running configured detector against uploaded media…</div>}
      {result && <DetectionResult result={result} filename={fileName} preview={preview} />}
    </section></>;
}

function DetectionResult({ result, filename, preview }) {
  const counts = Object.entries(result.counts);
  return <div className="detection-result"><div className="result-heading"><div><span className="eyebrow">DETECTION COMPLETE</span><h3>{filename}</h3></div><span className={`badge ${result.congestion.toLowerCase()}`}>{result.congestion} traffic</span></div>
    <div className="detection-body">{preview && <div className="preview-box"><img src={preview} alt="User-uploaded traffic media preview" />{result.detections.map((d, index) => <div key={index} className="bbox" style={{ left: `${d.box[0] / result.media_width * 100}%`, top: `${d.box[1] / result.media_height * 100}%`, width: `${(d.box[2] - d.box[0]) / result.media_width * 100}%`, height: `${(d.box[3] - d.box[1]) / result.media_height * 100}%` }} />)}</div>}<div className="detection-stats"><div className="det-total"><b>{result.total_vehicles}</b><small>objects detected across {result.sampled_frames} sampled frame(s)</small></div><div className="det-count-grid">{counts.map(([name, count]) => <div key={name}><span>{name}</span><b>{count}</b></div>)}</div><small className="muted-note">Bounding boxes and per-frame counts are returned by the configured detector. Video totals count detections across sampled frames.</small></div></div>
  </div>;
}

function AnalyticsPage({ analytics, refresh }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [filtered, setFiltered] = useState(null);
  const [filterError, setFilterError] = useState('');
  async function applyFilters(event) {
    event.preventDefault(); setFilterError('');
    try {
      const query = new URLSearchParams();
      if (start) query.set('start', new Date(`${start}T00:00:00`).toISOString());
      if (end) query.set('end', new Date(`${end}T23:59:59`).toISOString());
      setFiltered(await getJson(`/analytics?${query.toString()}`));
    } catch (error) { setFilterError(error.message); }
  }
  const data = filtered || analytics;
  const url = `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/reports.csv${start || end ? `?${new URLSearchParams({ ...(start ? { start: new Date(`${start}T00:00:00`).toISOString() } : {}), ...(end ? { end: new Date(`${end}T23:59:59`).toISOString() } : {}) })}` : ''}`;
  return <><div className="filter-bar"><form onSubmit={applyFilters}><label>From<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><label>To<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label><button className="button button-quiet" type="submit"><SlidersHorizontal size={14} /> Apply filter</button></form><a className="button button-primary" href={url} download><Download size={15} /> Download CSV</a></div>
    {filterError && <div className="alert error-alert"><AlertTriangle size={16} />{filterError}</div>}
    <div className="analytics-summary"><div><span>STORED SIMULATION SAMPLES</span><b>{fmt(data?.sample_count)}</b></div><div><span>ADAPTIVE AVG. WAIT</span><b>{data?.comparison?.adaptive_average_wait_seconds ?? 0}<small> sec</small></b></div><div><span>EST. WAIT IMPROVEMENT</span><b className="text-green">{data?.comparison?.improvement_percent ?? 0}<small>%</small></b></div></div>
    <div className="content-grid analytics-charts"><section className="panel chart-panel"><PanelHeader title="Hourly traffic patterns" tag="SIMULATION SNAPSHOTS" right={<span className="metric-caption">Vehicles and average wait</span>} /><div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data?.hourly || []} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}><CartesianGrid stroke="#202c3c" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="hour" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><YAxis yAxisId="left" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><Tooltip contentStyle={{ background: '#101d2d', border: '1px solid #27374a', borderRadius: 9, fontSize: 12 }} /><Area yAxisId="left" type="monotone" dataKey="vehicles" stroke="#31c5d4" fill="#31c5d4" fillOpacity=".12" /><Line yAxisId="right" type="monotone" dataKey="wait" stroke="#8792ff" strokeWidth={2} dot={false} /></ComposedChart></ResponsiveContainer></div></section>
      <section className="panel chart-panel"><PanelHeader title="Daily traffic patterns" tag="RECENT STORED DAYS" /><div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data?.daily || []} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}><CartesianGrid stroke="#202c3c" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 10 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#718196', fontSize: 11 }} /><Tooltip contentStyle={{ background: '#101d2d', border: '1px solid #27374a', borderRadius: 9, fontSize: 12 }} /><Area type="monotone" dataKey="vehicles" stroke="#9c80ff" fill="#9c80ff" fillOpacity=".13" /></AreaChart></ResponsiveContainer></div></section></div>
    <div className="content-grid analytics-lower"><section className="panel"><PanelHeader title="Intersection congestion" tag="AVERAGE QUEUE LENGTH" /><div className="heat-rows">{(data?.intersections || []).map((intersection) => <div className="heat-row" key={intersection.id}><span>{intersection.id.replaceAll('-', ' ')}</span><div className="heat-track"><span style={{ width: `${Math.min(100, intersection.average_queue / 1.2)}%` }} /></div><b>{intersection.average_queue}</b><small>avg. queue</small></div>)}</div></section><section className="panel"><PanelHeader title="Strategy comparison" tag="SIMULATED ESTIMATES" /><div className="strategy-compare"><div><span className="strategy-icon fixed"><Clock3 size={18} /></span><small>FIXED-TIME</small><b>{data?.comparison?.fixed_average_wait_seconds ?? 0}<i>sec avg. wait</i></b></div><ChevronRight size={18} /><div><span className="strategy-icon adaptive"><Activity size={18} /></span><small>ADAPTIVE</small><b>{data?.comparison?.adaptive_average_wait_seconds ?? 0}<i>sec avg. wait</i></b></div></div><div className="improvement-note"><ArrowDownRight size={15} />{data?.comparison?.improvement_percent ?? 0}% less estimated wait in adaptive strategy</div></section></div>
  </>;
}

function SettingsPage({ settings, setSettings, audit, managedIntersections, setManagedIntersections, identity, setIdentity, action, busy }) {
  const [form, setForm] = useState(settings || { minimum_green: 10, maximum_green: 45 });
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('admin');
  useEffect(() => { if (settings) setForm(settings); }, [settings]);
  async function signIn(event) {
    event.preventDefault();
    await action(async () => {
      const result = await postJson('/auth/login', { username, password, role });
      localStorage.setItem('flowsync_token', result.access_token);
      const signedIn = { username: result.username, role: result.role };
      localStorage.setItem('flowsync_identity', JSON.stringify(signedIn));
      setIdentity(signedIn);
    }, 'Signed in successfully.');
  }
  return <><div className="settings-grid"><section className="panel settings-card"><PanelHeader title="Access & roles" tag="PROTOTYPE AUTHENTICATION" /><p className="settings-description">Sign in to authorize signal overrides, emergency requests, or administrator-only settings.</p>
      {identity ? <div className="signed-in"><div className="avatar">{identity.username[0].toUpperCase()}</div><span><b>Signed in as {identity.username}</b><small>Role: {identity.role} · session held in memory on this server</small></span></div> : <form className="form-stack" onSubmit={signIn}><label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} required /></label><label>Role<select value={role} onChange={(e) => setRole(e.target.value)}><option value="admin">Administrator</option><option value="operator">Operator</option></select></label><label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label><button className="button button-primary" disabled={busy}><ShieldCheck size={15} /> Sign in</button><small className="form-hint">Use the password configured for your account role in the API environment.</small></form>}</section>
      <section className="panel settings-card"><PanelHeader title="Signal timing policy" tag="ADMIN ONLY" /><p className="settings-description">Adaptive green times respect these limits. Yellow clearance remains fixed at 3 seconds.</p><div className="timing-fields"><label>Minimum green<input type="number" min="5" max="30" value={form.minimum_green} onChange={(e) => setForm({ ...form, minimum_green: Number(e.target.value) })} /><small>seconds · 5–30</small></label><label>Maximum green<input type="number" min="20" max="90" value={form.maximum_green} onChange={(e) => setForm({ ...form, maximum_green: Number(e.target.value) })} /><small>seconds · 20–90</small></label></div><button className="button button-primary" disabled={busy || identity?.role !== 'admin'} onClick={() => action(async () => { const result = await (await request('/settings', { method: 'PATCH', body: JSON.stringify(form) })).json(); setSettings(result); }, 'Signal timing policy updated.')}>{identity?.role === 'admin' ? 'Save policy' : 'Administrator sign-in required'}</button></section></div>
    <div className="content-grid admin-grid"><section className="panel"><PanelHeader title="System health" tag="SIMULATION ENVIRONMENT" /><div className="health-rows">{[['API service', 'operational'], ['SQLite database', 'operational'], ['Traffic sensor feeds', 'simulation only'], ['YOLO model', settings ? 'optional · not configured' : 'checking']].map(([label, status]) => <div key={label}><span className="health-dot" /><b>{label}</b><small>{status}</small></div>)}</div></section>
      <section className="panel"><PanelHeader title="Operator audit log" tag={identity?.role === 'admin' ? 'LATEST 100 ACTIONS' : 'ADMIN ONLY'} /><div className="audit-list">{identity?.role !== 'admin' ? <div className="empty-state">Sign in as an administrator to view the audit log.</div> : audit.length ? audit.slice(0, 8).map((row) => <div className="audit-row" key={row.id}><span className="audit-dot" /><div><b>{row.action.replaceAll('_', ' ')}</b><small>{row.actor} · {new Date(row.created_at).toLocaleString()}</small></div></div>) : <div className="empty-state">No recorded actions yet.</div>}</div></section></div>
    <section className="panel intersection-admin-panel"><PanelHeader title="Manage intersections" tag="ADMIN ONLY" /><div className="managed-list">{identity?.role !== 'admin' ? <div className="empty-state">Sign in as an administrator to manage intersections.</div> : managedIntersections.map((intersection) => <div className="managed-row" key={intersection.id}><span className="junction-icon"><Layers3 size={15} /></span><div><b>{intersection.name}</b><small>{intersection.id}</small></div><span className={`badge ${intersection.enabled ? 'low' : 'medium'}`}>{intersection.enabled ? 'Enabled' : 'Paused'}</span><button className={`button ${intersection.enabled ? 'button-quiet' : 'button-primary'}`} disabled={busy} onClick={() => action(async () => { const updated = await (await request(`/admin/intersections/${intersection.id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !intersection.enabled }) })).json(); setManagedIntersections((current) => current.map((item) => item.id === updated.id ? updated : item)); }, `${intersection.name} ${intersection.enabled ? 'paused' : 'enabled'}.`)}>{intersection.enabled ? 'Pause' : 'Enable'}</button></div>)}</div></section>
  </>;
}

function EmptyChart() {
  return <div className="empty-chart"><BarChart3 size={25} /><span>Waiting for simulation samples</span><small>Run the simulation to collect traffic analytics.</small></div>;
}

function Loading() {
  return <div className="loading-state"><span className="spinner" /><b>Connecting to traffic network</b><small>Loading stored simulation data…</small></div>;
}

export default App;
