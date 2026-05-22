class GlobeApp {
  constructor() {
    this.viewer = null;
    this.dataStore = new DataStore();
    this.layerManager = null;
    this.countryCard = new CountryCard();
    this.capitalsManager = null;
    this.tradeManager = null;
    this.diplomacyManager = null;
    this.authManager = new AuthManager();
    this._initialized = false;
  }

  async start() {
    // Check Cesium loaded
    if (typeof Cesium === 'undefined') {
      throw new Error(
        'CesiumJS не загрузился. Проверьте подключение к интернету. ' +
        'CDN: unpkg.com/cesium — если заблокирован, используйте VPN или локальную копию.'
      );
    }

    // Load config (Cesium token) from API
    await loadConfig();

    // Set up auth change listener BEFORE init
    this.authManager.onAuthChange = (isAuthenticated, user) => {
      if (isAuthenticated && !this._initialized) {
        this._initializeApp();
      }
    };

    // Initialize auth — this checks tokens and shows/dismisses the gate
    await this.authManager.init();

    // If already authenticated, initialize immediately
    if (this.authManager.isAuthenticated()) {
      await this._initializeApp();
    }
    // Otherwise, the auth gate is visible and _initializeApp will be called
    // when the user successfully logs in (via onAuthChange callback)
  }

  async _initializeApp() {
    if (this._initialized) return;
    this._initialized = true;

    console.log('🔓 Auth confirmed, initializing TerraGlobe...');

    // Load data from API (non-blocking — globe works even if data fails)
    try {
      await this.dataStore.load();
    } catch (e) {
      console.warn('⚠️ Data load failed, globe will start empty:', e.message);
    }

    this.viewer = new Cesium.Viewer('cesiumContainer', {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      geocoder: false,
      infoBox: false,
      selectionIndicator: false,
    });
    console.log('🌍 Cesium запущен, версия:', Cesium.VERSION);

    this.layerManager = new LayerManager(this.viewer, this.dataStore);

    // Load layer and alliance data from API
    try {
      await this.layerManager.loadLayersData();
      await this.layerManager.loadAlliances();
    } catch (e) {
      console.warn('⚠️ Layer/alliance data failed to load:', e.message);
    }

    this.layerManager.createAllEntities();

    this.capitalsManager = new CapitalsManager(this.viewer, this.dataStore);
    try {
      await this.capitalsManager.load();
    } catch (e) {
      console.warn('⚠️ Capitals failed to load:', e.message);
    }

    this.tradeManager = new TradeManager(this.viewer, this.dataStore, this.capitalsManager);
    await this.tradeManager.load();

    this.diplomacyManager = new DiplomacyManager(this.viewer, this.dataStore);
    await this.diplomacyManager.load();

    setupUI(this.viewer, this.layerManager, this.countryCard, this.capitalsManager, this.tradeManager, this.diplomacyManager);

    console.log('✅ TerraGlobe готов к работе');
  }
}

const app = new GlobeApp();
app.start().catch(err => {
  console.error('❌ Fatal startup error:', err);
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;z-index:99999;';
  overlay.innerHTML = `
    <div style="color:#fff;text-align:center;padding:40px;max-width:500px;font-family:system-ui;">
      <h2 style="margin-bottom:16px;">⚠️ Ошибка загрузки</h2>
      <p style="opacity:0.8;margin-bottom:12px;">${err.message}</p>
      <p style="opacity:0.5;font-size:13px;">Откройте консоль браузера (F12) для подробностей.</p>
      <button onclick="location.reload()" style="margin-top:20px;padding:10px 24px;background:#667eea;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;">Перезагрузить</button>
    </div>`;
  document.body.appendChild(overlay);
});
