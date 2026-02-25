import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const PERIOD_ORDER = ['full_year']
const numberFormatter = new Intl.NumberFormat('en-US')
const percentFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})

const formatDate = (iso) => dateFormatter.format(new Date(iso))

async function fetchJson(path) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 60000) // 60 second timeout
  
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { signal: controller.signal })
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Request failed: ${response.status} - ${errorText}`)
    }
    return response.json()
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      throw new Error('Request timed out after 60 seconds')
    }
    throw err
  }
}

function MetricTable({ stats, onRowFocus, activeMetric }) {
  if (!stats) {
    return null
  }

  const { periods, sections, availableYears, selectedYear } = stats || {}
  // Show last 4 years
  const yearsToShow = (availableYears || []).slice(0, 4)
  
  // Safety check
  if (!periods || !sections || !Array.isArray(sections) || yearsToShow.length === 0) {
    return (
      <div className="table-card">
        <header className="table-card__header">
          <h2>Traffic Metrics</h2>
        </header>
        <p>Loading data... (Available years: {availableYears?.length || 0})</p>
      </div>
    )
  }
  
  // Ensure periods has full_year
  if (!periods.full_year) {
    return (
      <div className="table-card">
        <header className="table-card__header">
          <h2>Traffic Metrics</h2>
        </header>
        <p>No period data available</p>
      </div>
    )
  }

  const renderYearCells = (periodKey, rowValues) => {
    if (!rowValues || typeof rowValues !== 'object') {
      return yearsToShow.map((year) => (
        <td key={`${periodKey}-${year}`} className="cell current">—</td>
      ))
    }
    
    // Multi-year mode with delta
    return yearsToShow.flatMap((year) => {
      const yearData = rowValues[String(year)]
      if (!yearData) {
        return [
          <td key={`${periodKey}-${year}-value`} className="cell current">—</td>,
          <td key={`${periodKey}-${year}-delta`} className="cell change">—</td>
        ]
      }
      
      const value = yearData.value ?? 0
      const delta = yearData.delta
      const deltaClass = delta != null ? getChangeClass(delta) : ''
      
      return [
        <td key={`${periodKey}-${year}-value`} className="cell current">
          {numberFormatter.format(value)}
        </td>,
        <td key={`${periodKey}-${year}-delta`} className={`cell change ${deltaClass}`}>
          {delta == null ? '—' : delta === 'inf' || delta === Infinity ? '∞' : percentFormatter.format(delta / 100)}
        </td>
      ]
    })
  }

  return (
    <div className="table-card">
      <header className="table-card__header">
        <div>
          <h2>Traffic Metrics</h2>
          <span className="reference-window">
            Last 4 Years Comparison
          </span>
          <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem', marginBottom: 0 }}>
            Click on any metric row to view detailed insights below
          </p>
        </div>
        <div className="year-labels">
          {yearsToShow.map((year) => <span key={year}>{year}</span>)}
        </div>
      </header>
      <table className="metric-table">
        <thead>
          <tr>
            <th rowSpan={2} className="metric-name">Metric</th>
            {PERIOD_ORDER.map((periodKey) => (
              <th key={periodKey} colSpan={yearsToShow.length * 2} className="period-header">
                {periods[periodKey]?.label || 'Full Year'}
              </th>
            ))}
          </tr>
          <tr>
            {PERIOD_ORDER.flatMap((periodKey) =>
              yearsToShow.flatMap((year) => [
                <th key={`${periodKey}-${year}-value`}>{year}</th>,
                <th key={`${periodKey}-${year}-delta`}>Δ</th>
              ])
            )}
          </tr>
        </thead>
        <tbody>
          {sections.map((section) => (
            <Fragment key={section.id}>
              <tr key={`${section.id}-heading`} className="section-heading">
                <td colSpan={1 + PERIOD_ORDER.length * yearsToShow.length * 2}>{section.label}</td>
              </tr>
              {section.rows.map((row) => (
                <tr
                  key={row.id}
                  className={activeMetric?.id === row.id ? 'metric-row active' : 'metric-row'}
                  onClick={() => onRowFocus({ ...row, section: section.label })}
                >
                  <th scope="row" className="metric-name">{row.label}</th>
                  {PERIOD_ORDER.flatMap((periodKey) => {
                    const values = row.values[periodKey]
                    return renderYearCells(periodKey, values)
                  })}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function getChangeClass(value) {
  if (value == null) return ''
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return ''
}

function IncidentMap({ incidents, highlights = [] }) {
  const center = useMemo(() => ({ lat: 40.7128, lng: -74.006 }), [])

  const highlightMarkers = useMemo(
    () => highlights.filter((incident) => incident.latitude != null && incident.longitude != null),
    [highlights],
  )
  const highlightIds = new Set(highlightMarkers.map((incident) => incident.collisionId))
  const baseMarkers = incidents.filter((incident) => !highlightIds.has(incident.collisionId))

  return (
    <div className="map-card">
      <h3>Incident Map</h3>
      <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '-0.5rem', marginBottom: '0.75rem' }}>
        Recent traffic incidents with location markers
      </p>
      <div className="map-legend">
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#38bdf8' }}></span>
          <span>Injuries Only</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#f97316' }}></span>
          <span>Fatalities</span>
        </div>
        {highlightMarkers.length > 0 && (
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#a855f7' }}></span>
            <span>Search Results</span>
          </div>
        )}
      </div>
      <MapContainer center={center} zoom={11} scrollWheelZoom={false} className="map-frame">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {baseMarkers.map((incident) => (
          <CircleMarker
            key={incident.collisionId}
            center={{ lat: incident.latitude, lng: incident.longitude }}
            radius={6}
            pathOptions={{ color: incident.fatalities > 0 ? '#f97316' : '#38bdf8', fillOpacity: 0.8 }}
          >
            <Popup>
              <strong>{incident.borough}</strong>
              <br />
              Collision ID: {incident.collisionId}
              <br />
              Date: {incident.date}
              <br />
              Injuries: {incident.injuries}
              <br />
              Fatalities: {incident.fatalities}
            </Popup>
          </CircleMarker>
        ))}
        {highlightMarkers.map((incident) => (
          <CircleMarker
            key={`highlight-${incident.collisionId}`}
            center={{ lat: incident.latitude, lng: incident.longitude }}
            radius={7.5}
            pathOptions={{ color: '#a855f7', weight: 2, fillOpacity: 0.9 }}
          >
            <Popup>
              <strong>{incident.borough}</strong>
              <br />
              Collision ID: {incident.collisionId}
              <br />
              Date: {incident.date}
              <br />
              Injuries: {incident.injuries}
              <br />
              Fatalities: {incident.fatalities}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}

function MetricDetailPanel({ metric, stats, insights, insightsLoading }) {
  console.log('🎯 MetricDetailPanel rendered:', { 
    hasMetric: !!metric, 
    hasStats: !!stats, 
    hasInsights: !!insights,
    insightsLoading,
    insights: insights 
  })
  
  if (!metric || !stats) {
    return (
      <div className="detail-card">
        <h3>Metric Insight</h3>
        <p>Please select a metric from the traffic metrics table to start.</p>
      </div>
    )
  }

  const availableYears = stats.availableYears || []
  const yearsToShow = availableYears.slice(0, 4)

  return (
    <div className="detail-card">
      <h3>Metric Insights</h3>
      <h4>{metric.section} - {metric.label}</h4>
      <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '-0.75rem', marginBottom: '1rem' }}>
        Aggregated statistics and patterns for the selected metric
      </p>
      
      {/* Year-wise values */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h5 style={{ marginBottom: '0.5rem', fontSize: '0.9rem', opacity: 0.8 }}>Yearly Breakdown</h5>
        <ul>
          {PERIOD_ORDER.map((periodKey) => {
            const periodInfo = stats.periods?.[periodKey]
            const values = metric.values?.[periodKey]
            
            if (!values || typeof values !== 'object') {
              return null
            }
            
            return yearsToShow.map((year) => {
              const yearData = values[String(year)]
              if (!yearData) return null
              
              const value = yearData.value ?? 0
              
              return (
                <li key={`${periodKey}-${year}`}>
                  <span className="period-label">{year}</span>
                  <span>{numberFormatter.format(value)}</span>
                </li>
              )
            })
          })}
        </ul>
      </div>

      {/* Aggregated Insights */}
      {insightsLoading ? (
        <div style={{ opacity: 0.6 }}>Loading insights...</div>
      ) : insights ? (
        <div>
          <h5 style={{ marginBottom: '0.5rem', fontSize: '0.9rem', opacity: 0.8 }}>Aggregated Insights</h5>
          
          {insights.total_incidents > 0 ? (
            <>
              <div style={{ marginBottom: '1rem' }}>
                <strong>Total Incidents:</strong> {numberFormatter.format(insights.total_incidents)}
                {insights.total_injuries !== undefined && insights.total_injuries > 0 && (
                  <span style={{ marginLeft: '1rem' }}>
                    <strong>Total Injuries:</strong> {numberFormatter.format(insights.total_injuries)}
                  </span>
                )}
                {insights.total_fatalities !== undefined && insights.total_fatalities > 0 && (
                  <span style={{ marginLeft: '1rem' }}>
                    <strong>Total Fatalities:</strong> {numberFormatter.format(insights.total_fatalities)}
                  </span>
                )}
              </div>

          {insights.avg_injuries_per_incident > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Avg Injuries/Incident:</strong> {insights.avg_injuries_per_incident.toFixed(2)}
            </div>
          )}
          {insights.avg_fatalities_per_incident > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Avg Fatalities/Incident:</strong> {insights.avg_fatalities_per_incident.toFixed(2)}
            </div>
          )}

          {insights.top_contributing_factors && insights.top_contributing_factors.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Top Contributing Factors:</strong>
              <ul style={{ marginTop: '0.25rem', marginLeft: '1.5rem' }}>
                {insights.top_contributing_factors.map((item, idx) => (
                  <li key={idx} style={{ fontSize: '0.85rem' }}>
                    {item.factor}: {numberFormatter.format(item.count)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insights.top_streets && insights.top_streets.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Top Streets:</strong>
              <ul style={{ marginTop: '0.25rem', marginLeft: '1.5rem' }}>
                {insights.top_streets.map((item, idx) => (
                  <li key={idx} style={{ fontSize: '0.85rem' }}>
                    {item.street}: {numberFormatter.format(item.count)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insights.top_zip_codes && insights.top_zip_codes.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Top Zip Codes:</strong>
              <ul style={{ marginTop: '0.25rem', marginLeft: '1.5rem' }}>
                {insights.top_zip_codes.map((item, idx) => (
                  <li key={idx} style={{ fontSize: '0.85rem' }}>
                    {item.zip}: {numberFormatter.format(item.count)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insights.top_vehicle_types && insights.top_vehicle_types.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong>Top Vehicle Types:</strong>
              <ul style={{ marginTop: '0.25rem', marginLeft: '1.5rem' }}>
                {insights.top_vehicle_types.map((item, idx) => (
                  <li key={idx} style={{ fontSize: '0.85rem' }}>
                    {item.vehicle}: {numberFormatter.format(item.count)}
                  </li>
                ))}
              </ul>
            </div>
          )}
            </>
          ) : (
            <div style={{ opacity: 0.6, marginBottom: '1rem' }}>
              <strong>Total Incidents:</strong> 0 - No incidents found for this metric.
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}

function NLQQueryBox({
  queryText,
  onQueryChange,
  onRunQuery,
  result,
  loading,
  error,
}) {
  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (queryText.trim() && !loading) {
        onRunQuery()
      }
    }
  }

  return (
    <div className="nlq-card">
      <header className="nlq-card__header">
        <div>
          <h3>Natural Language Query</h3>
          <p className="nlq-subtitle">Ask questions about traffic collisions using natural language. Search by location, contributing factors, vehicle types, or any other criteria.</p>
        </div>
      </header>

      <div className="nlq-input-container">
        <div className="nlq-input-wrapper">
          <input
            type="text"
            className="nlq-input"
            placeholder="e.g., Find collisions with injuries in Brooklyn caused by aggressive driving..."
            value={queryText}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={loading}
          />
          <button
            type="button"
            className="nlq-search-button"
            onClick={onRunQuery}
            disabled={!queryText.trim() || loading}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </div>

      {error && <div className="nlq-error">{error}</div>}

      {result ? (
        <div className="nlq-body">
          <p className="nlq-summary">
            Found {result.totalMatches} matches · Showing top {result.rows.length} results
          </p>
          {result.rows.length > 0 ? (
            <table className="nlq-table">
              <thead>
                <tr>
                  {result.columns.map((column) => (
                    <th key={column.id}>{column.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.collisionId}>
                    {result.columns.map((column) => (
                      <td key={`${row.collisionId}-${column.id}`}>{row[column.id]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="nlq-empty">No records matched your query.</div>
          )}
        </div>
      ) : (
        <p className="nlq-placeholder">Enter a question above to search for traffic collisions.</p>
      )}
    </div>
  )
}

function App() {
  const [filters, setFilters] = useState({ borough: 'All', year: null })
  const [options, setOptions] = useState({ boroughs: ['All'], years: [] })
  const [stats, setStats] = useState(null)
  const [incidents, setIncidents] = useState([])
  const [activeMetric, setActiveMetric] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [queryText, setQueryText] = useState('')
  const [nlqResult, setNlqResult] = useState(null)
  const [nlqLoading, setNlqLoading] = useState(false)
  const [nlqError, setNlqError] = useState(null)
  const [highlightedIncidents, setHighlightedIncidents] = useState([])
  const [metricInsights, setMetricInsights] = useState(null)
  const [insightsLoading, setInsightsLoading] = useState(false)

  useEffect(() => {
    fetchJson('/api/filters')
      .then((payload) => {
        setOptions({
          boroughs: payload.boroughs || ['All'],
          years: payload.years || [],
        })
        // Set default year to most recent if available
        if (payload.years && payload.years.length > 0 && !filters.year) {
          setFilters((prev) => ({ ...prev, year: payload.years[0] }))
        }
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    let ignore = false
    setLoading(true)
    setError(null)

    async function loadStats() {
      try {
        let statsUrl = `/api/traffic-stats?borough=${encodeURIComponent(filters.borough)}`
        if (filters.year) {
          statsUrl += `&year=${filters.year}`
        }
        const statsResponse = await fetchJson(statsUrl)
        const incidentsResponse = await fetchJson(`/api/incidents?borough=${encodeURIComponent(filters.borough)}`)
        if (!ignore) {
          // Debug: log response
          console.log('Stats response:', statsResponse)
          console.log('Available years:', statsResponse.availableYears)
          console.log('Periods:', statsResponse.periods)
          console.log('Sections:', statsResponse.sections?.length)
          
          setStats(statsResponse)
          setIncidents(incidentsResponse.items || [])
          if (activeMetric) {
            const refreshedMetric = statsResponse.sections
              ?.flatMap((section) => section.rows?.map((row) => ({ ...row, section: section.label })) || [])
              .find((row) => row.id === activeMetric.id)
            setActiveMetric(refreshedMetric || null)
          }
        }
      } catch (err) {
        if (!ignore) {
          console.error('Error loading stats:', err)
          setError(err.message)
        }
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    }

    loadStats()
    return () => {
      ignore = true
    }
  }, [filters.borough, filters.year])

  // Fetch insights when metric is selected
  useEffect(() => {
    console.log('📊 Metric insights useEffect triggered:', { 
      activeMetric: activeMetric?.id, 
      borough: filters.borough,
      year: filters.year 
    })
    
    if (!activeMetric || !filters.borough) {
      console.log('⚠️ Skipping insights fetch - missing activeMetric or borough')
      setMetricInsights(null)
      return
    }

    let ignore = false
    setInsightsLoading(true)

    async function loadInsights() {
      try {
        let insightsUrl = `/api/metric-insights?borough=${encodeURIComponent(filters.borough)}&metric_id=${encodeURIComponent(activeMetric.id)}`
        if (filters.year) {
          insightsUrl += `&year=${filters.year}`
        }
        console.log('🔍 Fetching insights from:', insightsUrl)
        const insights = await fetchJson(insightsUrl)
        console.log('✅ Insights received:', insights)
        if (!ignore) {
          setMetricInsights(insights)
        }
      } catch (err) {
        if (!ignore) {
          console.error('❌ Error loading insights:', err)
          setMetricInsights(null)
        }
      } finally {
        if (!ignore) {
          setInsightsLoading(false)
        }
      }
    }

    loadInsights()
    return () => {
      ignore = true
    }
  }, [activeMetric?.id, filters.borough, filters.year])

  const handleFilterChange = (event) => {
    const { name, value } = event.target
    setFilters((prev) => ({ ...prev, [name]: value === '' ? null : value }))
  }

  const handleRunVectorSearch = useCallback(async () => {
    if (!queryText.trim()) {
      return
    }
    setNlqLoading(true)
    setNlqError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/vector-search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: queryText,
          limit: 10,
        }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        // Check if result has error message
        const errorMsg = result.error || `Request failed: ${response.status}`
        throw new Error(errorMsg)
      }
      
      // Check if result has error field (from backend)
      if (result.error) {
        throw new Error(result.error)
      }
      
      setNlqResult(result)
      setHighlightedIncidents(result.mapIncidents || [])
    } catch (err) {
      setNlqError(err.message || 'Vector search failed')
      setNlqResult(null)
      setHighlightedIncidents([])
    } finally {
      setNlqLoading(false)
    }
  }, [queryText])

  return (
    <div className="app">
      <header className="top-bar">
        <div className="branding">
          <img src="/vite.svg" alt="CityTraffic Logo" className="brand-icon" />
          <div>
            <h1>CityTraffic NLQ Dashboard</h1>
          </div>
        </div>
        <div className="filters">
          <label>
            <span>Patrol Borough</span>
            <select name="borough" value={filters.borough} onChange={handleFilterChange}>
              {options.boroughs.map((borough) => (
                <option key={borough}>{borough}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Year</span>
            <select name="year" value={filters.year || ''} onChange={handleFilterChange}>
              <option value="">All Years</option>
              {options.years.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <main className="content">
        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="loading-banner">Loading traffic insights…</div>}
        
        {/* Row 1: Traffic Metrics and Incident Map - Equal Width */}
        <div className="metrics-map-grid">
          <section className="metrics-panel">
            <MetricTable stats={stats} onRowFocus={setActiveMetric} activeMetric={activeMetric} />
          </section>
          <section className="map-panel">
            <IncidentMap incidents={incidents} highlights={highlightedIncidents} />
          </section>
        </div>

        {/* Row 2: Insights Container - Full Width */}
        {activeMetric && (
          <section className="insights-panel">
            <MetricDetailPanel 
              metric={activeMetric} 
              stats={stats} 
              insights={metricInsights}
              insightsLoading={insightsLoading}
            />
          </section>
        )}

        {/* Row 3: Chatbox - Full Width */}
        <section className="nlq-panel">
          <NLQQueryBox
            queryText={queryText}
            onQueryChange={setQueryText}
            onRunQuery={handleRunVectorSearch}
            result={nlqResult}
            loading={nlqLoading}
            error={nlqError}
          />
        </section>
      </main>
    </div>
  )
}

export default App
