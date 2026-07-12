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
    if (typeof Cesium === 'undefined') {
      throw new Error(
        'CesiumJS не загрузился. Проверьте подключение к интернету. ' +
        'CDN: unpkg.com/cesium — если заблокирован, используйте VPN или локальную копию.'
      );
    }

    // Load config (Cesium token) from API
    await loadConfig();

    this.authManager.onAuthChange = (isAuthenticated, user) => {
      if (isAuthenticated && !this._initialized) {
        this._initializeApp().catch(err => {
          console.error('❌ GlobeApp initialization failed:', err);
          this._initialized = false;
        });
      }
    };

    await this.authManager.init();

    if (this.authManager.isAuthenticated()) {
      await this._initializeApp();
    }
  }

  async _initializeApp() {
    if (this._initialized) return;
    this._initialized = true;

    console.log('🔓 Auth confirmed, initializing TerraGlobe...');

    // ── Step 1: Load country + GeoJSON data ──
    try {
      await this.dataStore.load();
    } catch (e) {
      console.warn('⚠️ Data load failed, globe will start empty:', e.message);
    }

    // ── Step 2a: Create imagery provider (ArcGIS primary — free, no token) ──
    let imageryProvider;

    // 1st try: ArcGIS World Imagery (free, no token needed — most reliable)
    try {
      imageryProvider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
        'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
        { enablePickFeatures: false }
      );
      console.log('🛰️ Using ArcGIS World Imagery');
    } catch (arcErr) {
      console.warn('⚠️ ArcGIS imagery failed:', arcErr.message);
      // 2nd try: Cesium Ion World Imagery (needs valid token)
      try {
        imageryProvider = await Cesium.createWorldImageryAsync();
        console.log('🛰️ Using Cesium Ion World Imagery');
      } catch (ionErr) {
        console.warn('⚠️ Cesium Ion imagery failed:', ionErr.message);
        // 3rd try: OpenStreetMap (always available, maps not satellite)
        imageryProvider = new Cesium.OpenStreetMapImageryProvider({
          url: 'https://tile.openstreetmap.org/'
        });
        console.log('🛰️ Using OpenStreetMap (fallback — no satellite)');
      }
    }

    // ── Step 2b: Create Cesium Viewer with performance + visuals ──
    // NOTE: CesiumJS 1.113 ignores `imageryProvider` option with baseLayerPicker:false.
    // We add imagery layers manually AFTER viewer creation.
    this.viewer = new Cesium.Viewer('cesiumContainer', {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      baseLayer: false,
      fullscreenButton: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      geocoder: false,
      infoBox: false,
      selectionIndicator: false,
    });

    console.log('🌍 Cesium запущен, версия:', Cesium.VERSION);

    // ── Add imagery layer manually (required in CesiumJS 1.113) ──
    this.viewer.imageryLayers.addImageryProvider(imageryProvider);
    const il = this.viewer.imageryLayers;
    console.log('🛰️ Imagery layers count:', il.length);
    console.log('🛰️ Base imagery provider:', il.get(0)?.imageryProvider?.constructor?.name || 'unknown');
    console.log('🛰️ Provider URL:', il.get(0)?.imageryProvider?.url || il.get(0)?.imageryProvider?._resource?.url || 'unknown');

    // ── Set terrain provider (Cesium World Terrain) with proxy fallback ──
    let terrainLoaded = false;

    // Try 1: Cesium World Terrain via Ion (may be geo-blocked)
    try {
      const terrain = await Promise.race([
        Cesium.CesiumTerrainProvider.fromIonAssetId(1),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Terrain load timeout')), 8000))
      ]);
      this.viewer.terrainProvider = terrain;
      terrainLoaded = true;
      console.log('🏔️ Cesium World Terrain loaded');
    } catch (e1) {
      console.warn('⚠️ Cesium Ion terrain failed:', e1.message);
    }

    // Try 2: Cesium terrain via our proxy (bypass geo-blocking)
    if (!terrainLoaded) {
      try {
        const proxyTerrain = await Promise.race([
          Cesium.CesiumTerrainProvider.fromUrl(
            '/api/proxy?url=' + encodeURIComponent('https://assets.cesium.com/1/'),
            { requestVertexNormals: true, requestWaterMask: true }
          ),
          new Promise((_, reject) => setTimeout(() => reject(new Error('Proxy terrain timeout')), 8000))
        ]);
        this.viewer.terrainProvider = proxyTerrain;
        terrainLoaded = true;
        console.log('🏔️ Terrain loaded via proxy');
      } catch (e2) {
        console.warn('⚠️ Proxy terrain failed:', e2.message);
      }
    }

    // Fallback: flat terrain
    if (!terrainLoaded) {
      this.viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
      console.log('🏔️ Using flat terrain (Ellipsoid)');
    }

    // ── Step 3: Scene tuning for realistic satellite look ──
    const scene = this.viewer.scene;
    const globe = scene.globe;

    // Globe base — dark blue space (not pure black) so night side has subtle glow
    globe.baseColor = Cesium.Color.fromCssColorString('#080818');

    // Realistic day/night lighting — THIS creates the day/night terminator
    globe.enableLighting = true;
    globe.showGroundAtmosphere = true;

    // Start with depth test off — only enable after terrain confirms loaded
    globe.depthTestAgainstTerrain = false;

    // Anti-aliasing (FXAA)
    scene.fxaa = true;
    scene.postProcessStages.fxaa.enabled = true;

    // Atmosphere — visible, natural look
    const atmosphere = scene.skyAtmosphere;
    atmosphere.show = true;
    atmosphere.hueShift = 0;
    atmosphere.saturationShift = 0;
    atmosphere.brightnessShift = 0;

    // Remove heavy fog — it darkens everything
    scene.fog.enabled = false;

    // CRITICAL: Allow Cesium to re-render periodically for real-time day/night.
    // maximumRenderTimeChange controls how often the scene re-renders.
    // Setting to 60 means: re-render every 60 simulated seconds of clock time.
    scene.requestRenderMode = true;
    scene.maximumRenderTimeChange = 60.0;
    scene.targetFrameRate = 30;

    // Sun/moon
    scene.sun.show = true;
    scene.moon.show = false;

    // Enable depth test against terrain only after terrain is confirmed ready
    this.viewer.scene.globe.terrainProviderChanged.addEventListener(() => {
      globe.depthTestAgainstTerrain = true;
      console.log('🏔️ Terrain confirmed — depth test enabled');
    });

    // ── Step 4: Initialize managers ──
    this.layerManager = new LayerManager(this.viewer, this.dataStore);
    this.capitalsManager = new CapitalsManager(this.viewer, this.dataStore);

    try {
      await this.layerManager.loadLayersData();
      await this.layerManager.loadAlliances();
    } catch (e) {
      console.warn('⚠️ Layer/alliance data failed to load:', e.message);
    }

    // Create country polygon entities — with simplified GeoJSON for perf
    this.layerManager.createAllEntities();

    try {
      await this.capitalsManager.load();
    } catch (e) {
      console.warn('⚠️ Capitals failed to load:', e.message);
    }

    this.tradeManager = new TradeManager(this.viewer, this.dataStore, this.capitalsManager);
    await this.tradeManager.load();

    this.diplomacyManager = new DiplomacyManager(this.viewer, this.dataStore);
    await this.diplomacyManager.load();

    // ── Step 5: Wire UI ──
    setupUI(this.viewer, this.layerManager, this.countryCard, this.capitalsManager, this.tradeManager, this.diplomacyManager);

    // ── Step 6: Trigger first render ──
    scene.requestRender();

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
