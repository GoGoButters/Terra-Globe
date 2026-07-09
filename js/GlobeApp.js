class GlobeApp {
  constructor() {
    this.viewer = null;
    this.dataStore = new DataStore();
    this.layerManager = null;
    this.countryCard = new CountryCard();
    this.capitalsManager = null;
    this.tradeManager = null;
    this.diplomacyManager = null;
  }

  async start() {
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
app.start();