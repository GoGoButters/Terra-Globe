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
      this.allianceData = {};

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

      // Filter rings with minimum area (removes degenerate sub-polygons from simplification)
      const validRings = rings.filter(ring => {
        if (!ring || ring.length < 3) return false;
        // Quick area check using shoelace formula
        let area = 0;
        for (let i = 0; i < ring.length; i++) {
          const j = (i + 1) % ring.length;
          area += ring[i][0] * ring[j][1];
          area -= ring[j][0] * ring[i][1];
        }
        return Math.abs(area) > 0.001; // min 0.001 square degrees
      });
      if (!validRings.length) return;

      // Each ring becomes its own entity to avoid passing Cartesian3[][]
      // (array of arrays) as the hierarchy, which CesiumJS interprets as
      // individual positions instead of rings, producing NaN in geometry math
      // and triggering "DeveloperError: normalized result is not a number".
      const entities = [];
      for (const ring of validRings) {
        const positions = Cesium.Cartesian3.fromDegreesArray(
          ring.flatMap(([lon, lat]) => [lon, lat])
        );
        if (!positions || positions.length < 3) continue;

        // Guard: skip if any position is degenerate (zero vector or NaN)
        const hasInvalid = positions.some(p =>
          !isFinite(p.x) || !isFinite(p.y) || !isFinite(p.z) ||
          (p.x === 0 && p.y === 0 && p.z === 0)
        );
        if (hasInvalid) continue;

        try {
          entities.push(this.viewer.entities.add({
            polygon: {
              hierarchy: positions,
              height: 0,
              material: Cesium.Color.WHITE.withAlpha(0.01),
              outline: true,
              outlineColor: Cesium.Color.WHITE.withAlpha(0.45),
              outlineWidth: 1.5,
            },
            _customData: {
              iso3,
              name: country.name,
            }
          }));
        } catch (e) {
          console.warn(`⚠️ Failed to create polygon entity for ${iso3}:`, e.message);
        }
      }

      if (entities.length > 0) {
        this.entities[iso3] = entities;
        this._createLabel(iso3, country.name, rings[0], rings);
      }
    });

    console.log('🌍 Полигонов:', Object.values(this.entities).flat().length,
                'Стран:', Object.keys(this.entities).length);
  }

  /**
   * Compute a robust centroid for a polygon ring.
   * Tries bounding-box center first (if inside polygon), otherwise
   * falls back to the ring vertex closest to the bbox center.
   */
  _computeCentroid(ring) {
    if (!ring || ring.length < 3) return ring?.[0] || [0, 0];
    
    // Step 1: Compute bounding box
    let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
    for (const [lon, lat] of ring) {
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
    }
    
    const cx = (minLon + maxLon) / 2;
    const cy = (minLat + maxLat) / 2;
    
    // Step 2: Check if center of bbox is inside polygon (ray casting)
    if (this._pointInPolygon(cx, cy, ring)) {
      return [cx, cy];
    }
    
    // Step 3: If not, find the point of the ring closest to the center
    let bestDist = Infinity;
    let bestPoint = ring[0];
    for (const [lon, lat] of ring) {
      const d = (lon - cx) ** 2 + (lat - cy) ** 2;
      if (d < bestDist) {
        bestDist = d;
        bestPoint = [lon, lat];
      }
    }
    return bestPoint;
  }

  /**
   * Ray-casting point-in-polygon test.
   */
  _pointInPolygon(x, y, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i][0], yi = polygon[i][1];
      const xj = polygon[j][0], yj = polygon[j][1];
      const intersect = ((yi > y) !== (yj > y)) &&
        (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  /**
   * Create country label using the polygon's computed centroid.
   * Uses a robust centroid algorithm for concave polygons (Chile, Norway, etc.)
   */
  _createLabel(iso3, name, ring, allRings) {
    if (!ring || ring.length < 3) return;

    // Compute area for font sizing
    let area = 0;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      area += ring[i][0] * ring[j][1] - ring[j][0] * ring[i][1];
    }
    area = Math.abs(area / 2) * 111.32 * 111.32; // km²
    if (isNaN(area) || !isFinite(area)) area = 0;

    // Use robust centroid
    const [centroidLon, centroidLat] = this._computeCentroid(ring);
    // Skip labels with invalid coordinates
    if (isNaN(centroidLon) || isNaN(centroidLat) ||
        !isFinite(centroidLon) || !isFinite(centroidLat)) return;

    // Font size based on country area
    let fontSize = 11;
    if (area > 1_000_000) fontSize = 18;
    else if (area > 500_000) fontSize = 16;
    else if (area > 200_000) fontSize = 14;
    else if (area > 50_000) fontSize = 12;

    // Distance-based visibility with zoom filtering for small countries
    let farDist = area > 500_000 ? 25_000_000 : area > 100_000 ? 12_000_000 : 6_000_000;
    if (area < 50_000) farDist = 3_000_000;
    if (isNaN(farDist) || farDist <= 0) farDist = 6_000_000;

    this.labels[iso3] = this.viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(centroidLon, centroidLat, 0),
      label: {
        text: name,
        font: `bold ${fontSize}px "Inter", "Segoe UI", sans-serif`,
        fillColor: Cesium.Color.WHITE.withAlpha(0.9),
        outlineColor: new Cesium.Color(0, 0, 0, 0.6),
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
        verticalOrigin: Cesium.VerticalOrigin.CENTER,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, farDist),
        translucencyByDistance: new Cesium.NearFarScalar(3e6, 1.0, farDist * 0.7, 0.0),
        pixelOffset: new Cesium.Cartesian2(0, 2),
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

  async switchLayer(layer) {
    this.currentLayer = layer;
    this.allianceMode = false;
    this.activeAlliances = {};

    // Fetch indicator values if not already cached
    if (!this.dataStore.indicatorCache[layer]) {
      await this.dataStore.getIndicatorMap(layer);
    }

    this.refreshColors();
    // Force Cesium to re-render
    this.viewer.scene.requestRender();
  }

  setAllianceMode(enabled) {
    this.allianceMode = enabled;
    if (!enabled) this.activeAlliances = {};
    this.refreshColors();
    this.viewer.scene.requestRender();
  }

  toggleAlliance(key, active) {
    this.activeAlliances[key] = active;
    this.refreshColors();
    this.viewer.scene.requestRender();
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
   * Get the numeric value for a given country from the current indicator cache.
   */
  _getIndicatorValue(iso3, layerCode) {
    const map = this.dataStore.indicatorCache[layerCode];
    if (!map) return undefined;
    return map[iso3];
  }

  getColor(value, layer) {
    if (value === undefined || value === null) return '#888888';

    // --- Экономика ---
    if (layer === 'income') {
      const income = String(value).toLowerCase();
      return { high: '#006837', 'upper-middle': '#78c679', 'lower-middle': '#fdae61', low: '#d7191c' }[income] || '#888888';
    }
    if (layer === 'gdp_per_capita') return this._gradient(value, [500, 5000, 15000, 35000, 80000]);
    if (layer === 'inflation') return this._gradient(value, [0, 5, 10, 25, 50], true);
    if (layer === 'gini') return this._gradient(value, [20, 35, 45, 55, 65], true);
    if (layer === 'unemployment') return this._gradient(value, [0, 5, 10, 20, 30], true);

    // --- Социум ---
    if (layer === 'hdi') {
      if (value >= 0.9) return '#1a9850';
      if (value >= 0.8) return '#91cf60';
      if (value >= 0.7) return '#fee08b';
      if (value >= 0.55) return '#fdae61';
      return '#d73027';
    }
    if (layer === 'life_expectancy') return this._gradient(value, [50, 60, 70, 78, 85]);
    if (layer === 'literacy') return this._gradient(value, [30, 60, 80, 95, 100]);
    if (layer === 'population_density') return this._gradient(value, [1, 50, 150, 400, 1000]);
    if (layer === 'urbanization') return this._gradient(value, [10, 30, 50, 70, 100]);

    // --- Политика ---
    if (layer === 'freedom') {
      if (value >= 70) return '#1a9850';
      if (value >= 40) return '#fee08b';
      return '#d73027';
    }
    if (layer === 'democracy_index') {
      if (value >= 8) return '#1a9850';
      if (value >= 6) return '#91cf60';
      if (value >= 4) return '#fdae61';
      return '#d73027';
    }
    if (layer === 'corruption') return this._gradient(value, [10, 30, 50, 70, 90]);
    if (layer === 'press_freedom') return this._gradient(value, [10, 30, 50, 70, 90], true);
    if (layer === 'political_stability') return this._gradient(value, [-3, -1, 0, 1, 2]);

    // --- Военные ---
    if (layer === 'military_power') return this._gradient(value, [0, 20, 40, 60, 100]);
    if (layer === 'military_budget') return this._gradient(value, [0, 2, 4, 6, 10]);
    if (layer === 'nuclear_weapons') {
      return value === 1 || value === true || value === '1' ? '#d73027' : '#1a9850';
    }

    return '#888888';
  }

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

  /**
   * Refresh all country polygon colors based on current mode + layer.
   * Uses indicatorCache in DataStore instead of entity custom data.
   */
  refreshColors() {
    const indicatorMap = this.dataStore.indicatorCache[this.currentLayer] || {};

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
          ? this._blendColors(colors).withAlpha(0.7)
          : Cesium.Color.WHITE.withAlpha(0.01);
      } else if (this.dataVisible) {
        const value = indicatorMap[d.iso3];
        const color = this.getColor(value, this.currentLayer);
        entity.polygon.material = Cesium.Color.fromCssColorString(color).withAlpha(0.75);
      } else {
        entity.polygon.material = Cesium.Color.WHITE.withAlpha(0.01);
      }
    });
  }

  setDataVisible(visible) {
    this.dataVisible = visible;
    this.refreshColors();
    this.viewer.scene.requestRender();
  }

  highlight(iso3) {
    if (this.highlightedIso && this.highlightedIso !== iso3) {
      (this.entities[this.highlightedIso] || []).forEach(e => {
        e.polygon.outlineColor = Cesium.Color.WHITE.withAlpha(0.25);
        e.polygon.outlineWidth = 1.0;
      });
    }
    (this.entities[iso3] || []).forEach(e => {
      e.polygon.outlineColor = Cesium.Color.fromCssColorString('#00d4ff').withAlpha(1.0);
      e.polygon.outlineWidth = 3.0;
      e.polygon.material = Cesium.Color.fromCssColorString('#00d4ff').withAlpha(0.15);
    });
    this.highlightedIso = iso3;
  }

  clearHighlight() {
    if (this.highlightedIso) {
      (this.entities[this.highlightedIso] || []).forEach(e => {
        e.polygon.outlineColor = Cesium.Color.WHITE.withAlpha(0.45);
        e.polygon.outlineWidth = 1.5;
      });
      this.highlightedIso = null;
      this.viewer.scene.requestRender();
    }
  }

  getEntity(iso3) {
    return (this.entities[iso3] || [])[0] || null;
  }
}
