// TerraGlobe configuration — API-driven
// Cesium Ion token is fetched from the backend at runtime

const API_BASE_URL = '/api';

// Cesium Ion token will be set after fetching /api/config
let CESIUM_ION_TOKEN = '';

async function loadConfig() {
  try {
    const config = await fetch(`${API_BASE_URL}/config`).then(r => r.json());
    if (config.cesium_ion_token) {
      CESIUM_ION_TOKEN = config.cesium_ion_token;
      Cesium.Ion.defaultAccessToken = CESIUM_ION_TOKEN;
    }
    console.log('📡 Config loaded, Cesium token:', CESIUM_ION_TOKEN ? 'set' : 'missing');
  } catch (e) {
    console.warn('⚠️ Could not load config from API, using defaults');
  }
}
