const API_BASE = '/api';

export async function fetchTrialSummary() {
  const res = await fetch(`${API_BASE}/trial/summary`);
  if (!res.ok) throw new Error('Failed to fetch trial summary');
  return res.json();
}

export async function fetchSites({ sortBy = 'risk_score', tier = null, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ sort_by: sortBy, limit, offset });
  if (tier) params.set('tier', tier);
  const res = await fetch(`${API_BASE}/sites?${params}`);
  if (!res.ok) throw new Error('Failed to fetch sites');
  return res.json();
}

export async function fetchSiteDetail(siteId) {
  const res = await fetch(`${API_BASE}/sites/${siteId}`);
  if (!res.ok) throw new Error('Failed to fetch site detail');
  return res.json();
}

export async function fetchDeviations({ siteId = null, severity = null, deviationType = null, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit, offset });
  if (siteId) params.set('site_id', siteId);
  if (severity) params.set('severity', severity);
  if (deviationType) params.set('deviation_type', deviationType);
  const res = await fetch(`${API_BASE}/deviations?${params}`);
  if (!res.ok) throw new Error('Failed to fetch deviations');
  return res.json();
}

export async function fetchCapaReport(siteId) {
  const res = await fetch(`${API_BASE}/capa/${siteId}`);
  if (!res.ok) throw new Error('Failed to fetch CAPA report');
  return res.json();
}

export async function fetchTrends() {
  const res = await fetch(`${API_BASE}/trends`);
  if (!res.ok) throw new Error('Failed to fetch trends');
  return res.json();
}
