class LayerManager {
  constructor(viewer, dataStore) {
    this.viewer = viewer;
    this.dataStore = dataStore;
    this.entities = {};
    this.labels = {};
    this.currentLayer = 'income';
    this.highlightedIso = null;
    this.dataVisible = false;
    this.allianceMode = false;
    this.activeAlliances = {};
    this.allianceData = {};
    this.layersData = null;
  }

  async loadLayersData() {
    try {
      this.layersData = await API.getIndicatorDefinitions();
      console.log('📊 Загружены слои:', this.layersData.length);
    } catch (e) {
      console.error('Ошибка загрузки слоёв:', e);
    }
  }

  async loadAlliances() {
    try {
      const alliancesList = await API.getAlliances();
      // Convert array to keyed object for compatibility with existing code
      this.allianceData = {};

      // Fetch all alliance details in parallel
      const details = await Promise.allSettled(
        alliancesList.map(a => API.getAlliance(a.code))
      );

      details.forEach((result, i) => {
        if (result.status === 'fulfilled' && result.value) {
          const detail = result.value;
          const code = alliancesList[i].code;
          this.allianceData[code] = {
            name: detail.name,
            color: detail.color,
            founded: detail.founded,
            headquarters: detail.headquarters,
            info: detail.info,
            features: detail.features,
            members: detail.members.map(m => m.country_iso3),
          };
        }
      });

      console.log('🌐 Загружены альянсы:', Object.keys(this.allianceData));
    } catch (e) {
      console.error('Ошибка загрузки альянсов:', e);
    }
  }

  createAllEntities() {
    const codes = this.dataStore.getAllCodes();
    codes.forEach(iso3 => {
      const country = this.dataStore.get(iso3);
      if (!country || !country.geometry) return;

      const rings = this.extractRings(country.geometry);
      if (!rings.length) return;

      const countryEntities = [];
      rings.forEach(ring => {
        if (!ring || ring.length < 3) return;

        const hierarchy = Cesium.Cartesian3.fromDegreesArray(
          ring.flatMap(([lon, lat]) => [lon, lat])
        );

        // Вот здесь была проблема — всегда брался цвет из getColor
        // Теперь используем dataVisible
        const color = this.dataVisible ? this.getColor(country, this.currentLayer) : '#888888';

        countryEntities.push(
          this.viewer.entities.add({
            polygon: {
              hierarchy,
              height: 0,
              // Если dataVisible = false, делаем полигон почти прозрачным
              material: this.dataVisible
                ? Cesium.Color.fromCssColorString(color).withAlpha(0.8)
                : Cesium.Color.WHITE.withAlpha(0.01),
              outline: true,
              outlineColor: Cesium.Color.WHITE.withAlpha(0.8),
              outlineWidth: 1.5,
            },
            _customData: {
              iso3, name: country.name,
              income: country.income,
              gdp: country.gdp, pop: country.pop, hdi: country.hdi,
              freedom: country.freedom, gdp_per_capita: country.gdp_per_capita,
              inflation: country.inflation, gini: country.gini,
              unemployment: country.unemployment, life_expectancy: country.life_expectancy,
              literacy: country.literacy, population_density: country.population_density,
              urbanization: country.urbanization, democracy_index: country.democracy_index,
              corruption: country.corruption, press_freedom: country.press_freedom,
              political_stability: country.political_stability,
              military_power: country.military_power,
              military_budget: country.military_budget,
              nuclear_weapons: country.nuclear_weapons,
              // indicators object for API format compatibility
              indicators: country.indicators || {}
            }
          })
        );
      });

      if (countryEntities.length) this.entities[iso3] = countryEntities;
      this._createLabel(iso3, country.name, rings[0]);
    });

    console.log('🌍 Полигонов:', Object.values(this.entities).flat().length,
                'Стран:', Object.keys(this.entities).length);
  }

  _createLabel(iso3, name, ring) {
    if (!ring || ring.length < 3) return;

    let sumLon = 0, sumLat = 0;
    ring.forEach(([lon, lat]) => { sumLon += lon; sumLat += lat; });
    const centerLon = sumLon / ring.length;
    const centerLat = sumLat / ring.length;

    let signedArea = 0;
    for (let i = 0; i < ring.length; i++) {
      const [x1, y1] = ring[i];
      const [x2, y2] = ring[(i + 1) % ring.length];
      signedArea += x1 * y2 - x2 * y1;
    }
    const area = Math.abs(signedArea / 2) * 111.32 * 111.32;

    let fontSize = 12;
    if (area > 1_000_000) fontSize = 20;
    else if (area > 500_000) fontSize = 18;
    else if (area > 200_000) fontSize = 16;
    else if (area > 50_000) fontSize = 14;

    const farDist = area > 200_000 ? 20_000_000 : 8_000_000;

    this.labels[iso3] = this.viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(centerLon, centerLat, 0),
      label: {
        text: name,
        font: `bold ${fontSize}px "Inter", "Segoe UI", sans-serif`,
        fillColor: Cesium.Color.WHITE.withAlpha(0.95),
        outlineColor: Cesium.Color.BLACK.withAlpha(0.7),
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
        verticalOrigin: Cesium.VerticalOrigin.CENTER,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, farDist),
        translucencyByDistance: new Cesium.NearFarScalar(1e6, 1.0, farDist, 0.4),
      },
    });
  }

  extractRings(geometry) {
    if (!geometry) return [];
    if (geometry.type === 'GeometryCollection') {
      return (geometry.geometries || []).flatMap(g => this.extractRings(g));
    }
    if (geometry.type === 'Polygon' && geometry.coordinates[0]) return [geometry.coordinates[0]];
    if (geometry.type === 'MultiPolygon') {
      return geometry.coordinates.filter(poly => poly[0] && Array.isArray(poly[0])).map(poly => poly[0]);
    }
    return [];
  }

  switchLayer(layer) {
    this.currentLayer = layer;
    this.allianceMode = false;
    this.activeAlliances = {};
    this.refreshColors();
  }

  setAllianceMode(enabled) {
    this.allianceMode = enabled;
    if (!enabled) this.activeAlliances = {};
    this.refreshColors();
  }

  toggleAlliance(key, active) {
    this.activeAlliances[key] = active;
    this.refreshColors();
  }

  _blendColors(colors) {
    if (!colors.length) return null;
    if (colors.length === 1) return Cesium.Color.fromCssColorString(colors[0]);
    let r = 0, g = 0, b = 0;
    colors.forEach(hex => {
      const c = Cesium.Color.fromCssColorString(hex);
      r += c.red; g += c.green; b += c.blue;
    });
    return new Cesium.Color(r / colors.length, g / colors.length, b / colors.length);
  }

  /**
   * Основной метод получения цвета.
   * Работает как с flat data (старый формат), так и с API response (indicators object).
   */
  _getValue(d, field) {
    // Try flat format first (legacy/static data)
    if (d[field] !== undefined) return d[field];
    // Try API format (nested in indicators)
    if (d.indicators && d.indicators[field] !== undefined) return d.indicators[field];
    return undefined;
  }

  getColor(d, layer) {
    if (!d) return '#888888';

    // --- Экономика ---
    if (layer === 'income') {
      const income = this._getValue(d, 'income');
      return { high: '#006837', 'upper-middle': '#78c679', 'lower-middle': '#fdae61', low: '#d7191c' }[income] || '#888888';
    }
    if (layer === 'gdp_per_capita') return this._gradient(this._getValue(d, 'gdp_per_capita'), [500, 5000, 15000, 35000, 80000]);
    if (layer === 'inflation') return this._gradient(this._getValue(d, 'inflation'), [0, 5, 10, 25, 50], true);
    if (layer === 'gini') return this._gradient(this._getValue(d, 'gini'), [20, 35, 45, 55, 65], true);
    if (layer === 'unemployment') return this._gradient(this._getValue(d, 'unemployment'), [0, 5, 10, 20, 30], true);

    // --- Социум ---
    if (layer === 'hdi') {
      const hdi = this._getValue(d, 'hdi');
      if (hdi === undefined) return '#888888';
      if (hdi >= 0.9) return '#1a9850';
      if (hdi >= 0.8) return '#91cf60';
      if (hdi >= 0.7) return '#fee08b';
      if (hdi >= 0.55) return '#fdae61';
      return '#d73027';
    }
    if (layer === 'life_expectancy') return this._gradient(this._getValue(d, 'life_expectancy'), [50, 60, 70, 78, 85]);
    if (layer === 'literacy') return this._gradient(this._getValue(d, 'literacy'), [30, 60, 80, 95, 100]);
    if (layer === 'population_density') return this._gradient(this._getValue(d, 'population_density'), [1, 50, 150, 400, 1000]);
    if (layer === 'urbanization') return this._gradient(this._getValue(d, 'urbanization'), [10, 30, 50, 70, 100]);

    // --- Политика ---
    if (layer === 'freedom') {
      const freedom = this._getValue(d, 'freedom');
      if (freedom === undefined) return '#888888';
      if (freedom >= 70) return '#1a9850';
      if (freedom >= 40) return '#fee08b';
      return '#d73027';
    }
    if (layer === 'democracy_index') {
      const di = this._getValue(d, 'democracy_index');
      if (di === undefined) return '#888888';
      if (di >= 8) return '#1a9850';
      if (di >= 6) return '#91cf60';
      if (di >= 4) return '#fdae61';
      return '#d73027';
    }
    if (layer === 'corruption') return this._gradient(this._getValue(d, 'corruption'), [10, 30, 50, 70, 90]);
    if (layer === 'press_freedom') return this._gradient(this._getValue(d, 'press_freedom'), [10, 30, 50, 70, 90], true);
    if (layer === 'political_stability') return this._gradient(this._getValue(d, 'political_stability'), [-3, -1, 0, 1, 2]);

    // --- Военные ---
    if (layer === 'military_power') return this._gradient(this._getValue(d, 'military_power'), [0, 20, 40, 60, 100]);
    if (layer === 'military_budget') return this._gradient(this._getValue(d, 'military_budget'), [0, 2, 4, 6, 10]);
    if (layer === 'nuclear_weapons') {
      const nw = this._getValue(d, 'nuclear_weapons');
      return nw === 1 ? '#d73027' : '#1a9850';
    }

    return '#888888';
  }

  /**
   * Градиентная раскраска по диапазонам.
   * @param {number} value — значение
   * @param {number[]} stops — массив порогов (по возрастанию)
   * @param {boolean} [reverse=false] — true если "меньше = лучше" (unemployment, inflation)
   */
  _gradient(value, stops, reverse = false) {
    if (value === undefined || value === null || isNaN(value)) return '#888888';
    const colors = reverse
      ? ['#1a9850', '#91cf60', '#fee08b', '#fdae61', '#d73027']
      : ['#d73027', '#fdae61', '#fee08b', '#91cf60', '#1a9850'];

    for (let i = stops.length - 1; i >= 0; i--) {
      if (value >= stops[i]) return colors[i];
    }
    return colors[0];
  }

  refreshColors() {
    Object.values(this.entities).flat().forEach(entity => {
      const d = entity._customData;
      if (!d) return;

      if (this.allianceMode && Object.keys(this.activeAlliances).length > 0) {
        const colors = [];
        Object.entries(this.activeAlliances).forEach(([key, active]) => {
          if (active && this.allianceData[key]) {
            if (this.allianceData[key].members.includes(d.iso3)) {
              colors.push(this.allianceData[key].color);
            }
          }
        });
        entity.polygon.material = colors.length > 0
          ? this._blendColors(colors).withAlpha(0.85)
          : Cesium.Color.WHITE.withAlpha(0.01);
      } else if (this.dataVisible) {
        entity.polygon.material = Cesium.Color.fromCssColorString(
          this.getColor(d, this.currentLayer)
        ).withAlpha(0.8);
      } else {
        entity.polygon.material = Cesium.Color.WHITE.withAlpha(0.01);
      }
    });
  }

  setDataVisible(visible) {
    this.dataVisible = visible;
    this.refreshColors();
  }

  highlight(iso3) {
    if (this.highlightedIso && this.highlightedIso !== iso3) {
      (this.entities[this.highlightedIso] || []).forEach(e => {
        e.polygon.outlineColor = Cesium.Color.WHITE.withAlpha(0.8);
        e.polygon.outlineWidth = 1.5;
      });
    }
    (this.entities[iso3] || []).forEach(e => {
      e.polygon.outlineColor = Cesium.Color.YELLOW.withAlpha(1.0);
      e.polygon.outlineWidth = 2.5;
    });
    this.highlightedIso = iso3;
  }

  clearHighlight() {
    if (this.highlightedIso) {
      (this.entities[this.highlightedIso] || []).forEach(e => {
        e.polygon.outlineColor = Cesium.Color.WHITE.withAlpha(0.8);
        e.polygon.outlineWidth = 1.5;
      });
      this.highlightedIso = null;
    }
  }

  getEntity(iso3) {
    return (this.entities[iso3] || [])[0] || null;
  }
}