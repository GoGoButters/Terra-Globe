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
  }

  async start() {
    // Load config (Cesium token) from API
    await loadConfig();

    // Initialize auth
    await this.authManager.init();

    // Load data from API
    await this.dataStore.load();

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
    await this.layerManager.loadLayersData();
    await this.layerManager.loadAlliances();

    this.layerManager.createAllEntities();

    this.capitalsManager = new CapitalsManager(this.viewer, this.dataStore);
    await this.capitalsManager.load();

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
  overlay.innerHTML = `<div style="color:#fff;text-align:center;padding:40px;max-width:500px;"><h2>⚠️ Ошибка загрузки</h2><p style="opacity:0.7;margin-top:12px;">${err.message || 'Не удалось инициализировать приложение. Проверьте подключение к серверу.'}</p><p style="opacity:0.5;margin-top:20px;font-size:13px;">Откройте консоль браузера (F12) для подробностей.</p></div>`;
  document.body.appendChild(overlay);
});
