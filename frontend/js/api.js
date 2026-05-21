/**
 * API client with JWT auth, auto-refresh, and error handling.
 * All backend requests go through this module.
 */

const API = {
  baseUrl: '/api',
  accessToken: null,
  refreshToken: null,
  refreshPromise: null,

  // ── Token management ──
  setTokens(access, refresh) {
    this.accessToken = access;
    this.refreshToken = refresh;
    localStorage.setItem('tg_access_token', access);
    localStorage.setItem('tg_refresh_token', refresh);
  },

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('tg_access_token');
    localStorage.removeItem('tg_refresh_token');
  },

  loadTokens() {
    this.accessToken = localStorage.getItem('tg_access_token');
    this.refreshToken = localStorage.getItem('tg_refresh_token');
    return !!this.accessToken;
  },

  isAuthenticated() {
    return !!this.accessToken;
  },

  // ── Core fetch with auto-refresh ──
  async fetch(path, options = {}) {
    const url = `${this.baseUrl}${path}`;

    // If refresh is in progress, wait for it before making the request
    if (this.refreshPromise) {
      await this.refreshPromise;
    }

    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    let response = await fetch(url, { ...options, headers });

    // Handle 401 with auto-refresh
    if (response.status === 401 && this.refreshToken) {
      await this._refreshAccessToken();
      // Retry with new token
      headers['Authorization'] = `Bearer ${this.accessToken}`;
      response = await fetch(url, { ...options, headers });
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(response.status, error.detail || 'Request failed');
    }

    return response.json();
  },

  async _refreshAccessToken() {
    // Prevent concurrent refresh attempts
    if (this.refreshPromise) {
      await this.refreshPromise;
      return;
    }

    this.refreshPromise = (async () => {
      try {
        const resp = await fetch(`${this.baseUrl}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        });

        if (!resp.ok) {
          this.clearTokens();
          throw new ApiError(401, 'Refresh token expired');
        }

        const data = await resp.json();
        this.setTokens(data.access_token, data.refresh_token);
      } finally {
        this.refreshPromise = null;
      }
    })();

    await this.refreshPromise;
  },

  // ── Convenience methods ──
  async get(path) { return this.fetch(path, { method: 'GET' }); },
  async post(path, body) { return this.fetch(path, { method: 'POST', body: JSON.stringify(body) }); },

  // ── Auth endpoints ──
  async register(email, username, password) {
    const data = await this.post('/auth/register', { email, username, password });
    this.setTokens(data.access_token, data.refresh_token);
    return data;
  },

  async login(email, password) {
    const data = await this.post('/auth/login', { email, password });
    this.setTokens(data.access_token, data.refresh_token);
    return data;
  },

  async logout() {
    if (this.refreshToken) {
      await this.post('/auth/logout', { refresh_token: this.refreshToken }).catch(() => {});
    }
    this.clearTokens();
  },

  async getMe() { return this.get('/auth/me'); },

  // ── Config ──
  async getConfig() { return this.get('/config'); },

  // ── Countries ──
  async getCountries(bbox) {
    const params = bbox ? `?bbox=${encodeURIComponent(bbox)}` : '';
    return this.get(`/countries${params}`);
  },

  async getCountry(iso3) { return this.get(`/countries/${iso3}`); },

  async getCountriesGeoJSON(simplify) {
    const params = simplify ? `?simplify=${simplify}` : '';
    return this.get(`/countries/geojson${params}`);
  },

  // ── Indicators ──
  async getIndicatorDefinitions() { return this.get('/indicators/definitions'); },

  async getIndicatorValues(codes, countries, year) {
    const params = new URLSearchParams();
    if (codes) params.set('codes', codes);
    if (countries) params.set('countries', countries);
    if (year) params.set('year', year);
    const qs = params.toString();
    return this.get(`/indicators/values${qs ? '?' + qs : ''}`);
  },

  async getIndicatorMap(code, year) {
    const params = year ? `?year=${year}` : '';
    return this.get(`/indicators/${code}/map${params}`);
  },

  // ── Alliances ──
  async getAlliances() { return this.get('/alliances'); },

  async getAlliance(code) { return this.get(`/alliances/${code}`); },

  // ── Trade ──
  async getTradeSummary(iso3, year) {
    const params = year ? `?year=${year}` : '';
    return this.get(`/trade/${iso3}${params}`);
  },

  async getTradePartners(iso3, year, limit) {
    const params = new URLSearchParams();
    if (year) params.set('year', year);
    if (limit) params.set('limit', limit);
    const qs = params.toString();
    return this.get(`/trade/${iso3}/partners${qs ? '?' + qs : ''}`);
  },

  async getTradeCategories(iso3, year) {
    const params = year ? `?year=${year}` : '';
    return this.get(`/trade/${iso3}/categories${params}`);
  },

  // ── Diplomacy ──
  async getDiplomacy(country) {
    const params = country ? `?country=${country}` : '';
    return this.get(`/diplomacy${params}`);
  },

  async getDiplomaticRelations(iso3A, iso3B) {
    return this.get(`/diplomacy/${iso3A}/${iso3B}`);
  },
};

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}
