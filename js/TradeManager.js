class TradeManager {
  constructor(viewer, dataStore, capitalsManager) {
    this.viewer = viewer;
    this.dataStore = dataStore;
    this.capitalsManager = capitalsManager;
    this.tradeData = {};
    this.tradeEntities = [];
    this.activeIso3 = null;
  }

  async load() {
    try {
      const res = await fetch('data/trade_data.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.tradeData = await res.json();
      console.log('📊 Загружены торговые данные:', Object.keys(this.tradeData).length, 'стран');
    } catch (e) {
      console.error('❌ Ошибка загрузки trade_data.json:', e);
    }
  }

  showTrade(iso3) {
    this.clear();
    this.activeIso3 = iso3;
    const data = this.tradeData[iso3];
    if (!data) return;

    const sourceCapital = this._getCapitalCoords(iso3);
    if (!sourceCapital) return;

    data.partners.forEach(partner => {
      const targetCapital = this._getCapitalCoords(partner.iso3);
      if (!targetCapital) return;

      const exportPct = data.total_exports > 0 ? ((partner.export / data.total_exports) * 100).toFixed(1) : 0;
      const importPct = data.total_imports > 0 ? ((partner.import / data.total_imports) * 100).toFixed(1) : 0;

      // Ортодромия
      const path = this._computeGreatCirclePath(
        sourceCapital.lat, sourceCapital.lon,
        targetCapital.lat, targetCapital.lon,
        100
      );

      const STRIPE_HEIGHT = 600000;
      const midIndex = Math.floor(path.length / 2);
      const midPoint = path[midIndex];
      const nextPoint = path[Math.min(midIndex + 2, path.length - 1)];
      const dx = nextPoint.lon - midPoint.lon;
      const dy = nextPoint.lat - midPoint.lat;
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const perpX = -dy / len;
      const perpY = dx / len;
      const OFFSET = 0.2;

      // --- Зелёная полоса (экспорт) ---
      const greenPath = path.map(p => ({
        lon: p.lon + perpX * OFFSET,
        lat: p.lat + perpY * OFFSET
      }));

      const greenPoints = greenPath.map((p, i) => {
        const t = i / (greenPath.length - 1);
        const h = STRIPE_HEIGHT * 4 * t * (1 - t);
        return Cesium.Cartesian3.fromDegrees(p.lon, p.lat, h);
      });

      this.tradeEntities.push(this.viewer.entities.add({
        polyline: {
          positions: greenPoints,
          width: 3,
          material: Cesium.Color.fromCssColorString('#4caf50').withAlpha(0.9),
          clampToGround: false
        }
      }));

      // --- Красная полоса (импорт) ---
      const redPath = path.map(p => ({
        lon: p.lon - perpX * OFFSET,
        lat: p.lat - perpY * OFFSET
      }));

      const redPoints = redPath.map((p, i) => {
        const t = i / (redPath.length - 1);
        const h = STRIPE_HEIGHT * 4 * t * (1 - t);
        return Cesium.Cartesian3.fromDegrees(p.lon, p.lat, h);
      });

      this.tradeEntities.push(this.viewer.entities.add({
        polyline: {
          positions: redPoints,
          width: 3,
          material: Cesium.Color.fromCssColorString('#f44336').withAlpha(0.9),
          clampToGround: false
        }
      }));

      // --- Подписи ПРЯМО НАД полосами (без смещения по нормали) ---
      const greenMid = greenPath[Math.floor(greenPath.length / 2)];
      const greenH = STRIPE_HEIGHT * 0.7 + 50000;

      // Зелёная подпись
      const greenLabelPos = Cesium.Cartesian3.fromDegrees(greenMid.lon, greenMid.lat, greenH);
      this.tradeEntities.push(this.viewer.entities.add({
        position: greenLabelPos,
        label: {
          text: `↑ $${partner.export} млрд (${exportPct}%)`,
          font: 'bold 12px "Segoe UI", sans-serif',
          fillColor: Cesium.Color.fromCssColorString('#4caf50'),
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 30000000)
        }
      }));

      // Соединительная линия от полосы к подписи (зелёная)
      const greenMidLow = Cesium.Cartesian3.fromDegrees(greenMid.lon, greenMid.lat, STRIPE_HEIGHT * 0.7);
      this.tradeEntities.push(this.viewer.entities.add({
        polyline: {
          positions: [greenMidLow, greenLabelPos],
          width: 1.5,
          material: Cesium.Color.fromCssColorString('#4caf50').withAlpha(0.6),
          clampToGround: false
        }
      }));

      // Красная подпись
      const redMid = redPath[Math.floor(redPath.length / 2)];
      const redH = STRIPE_HEIGHT * 0.7 + 50000;

      const redLabelPos = Cesium.Cartesian3.fromDegrees(redMid.lon, redMid.lat, redH);
      this.tradeEntities.push(this.viewer.entities.add({
        position: redLabelPos,
        label: {
          text: `↓ $${partner.import} млрд (${importPct}%)`,
          font: 'bold 12px "Segoe UI", sans-serif',
          fillColor: Cesium.Color.fromCssColorString('#f44336'),
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 30000000)
        }
      }));

      // Соединительная линия (красная)
      const redMidLow = Cesium.Cartesian3.fromDegrees(redMid.lon, redMid.lat, STRIPE_HEIGHT * 0.7);
      this.tradeEntities.push(this.viewer.entities.add({
        polyline: {
          positions: [redMidLow, redLabelPos],
          width: 1.5,
          material: Cesium.Color.fromCssColorString('#f44336').withAlpha(0.6),
          clampToGround: false
        }
      }));
    });

    this._fillLeftPanel(data);
  }

  _computeGreatCirclePath(lat1, lon1, lat2, lon2, numPoints) {
    const toRad = Math.PI / 180;
    const toDeg = 180 / Math.PI;
    const lat1r = lat1 * toRad, lon1r = lon1 * toRad;
    const lat2r = lat2 * toRad, lon2r = lon2 * toRad;
    const delta = Math.acos(
      Math.sin(lat1r) * Math.sin(lat2r) +
      Math.cos(lat1r) * Math.cos(lat2r) * Math.cos(lon2r - lon1r)
    );
    const path = [];
    if (delta < 0.001) {
      for (let i = 0; i <= numPoints; i++) {
        const t = i / numPoints;
        path.push({ lat: lat1 + (lat2 - lat1) * t, lon: lon1 + (lon2 - lon1) * t });
      }
      return path;
    }
    const sinDelta = Math.sin(delta);
    for (let i = 0; i <= numPoints; i++) {
      const t = i / numPoints;
      const a = Math.sin((1 - t) * delta) / sinDelta;
      const b = Math.sin(t * delta) / sinDelta;
      const x = a * Math.cos(lat1r) * Math.cos(lon1r) + b * Math.cos(lat2r) * Math.cos(lon2r);
      const y = a * Math.cos(lat1r) * Math.sin(lon1r) + b * Math.cos(lat2r) * Math.sin(lon2r);
      const z = a * Math.sin(lat1r) + b * Math.sin(lat2r);
      path.push({
        lat: Math.atan2(z, Math.sqrt(x * x + y * y)) * toDeg,
        lon: Math.atan2(y, x) * toDeg
      });
    }
    return path;
  }

  _getCapitalCoords(iso3) {
    if (!this.capitalsManager || !this.capitalsManager.capitalsData) return null;
    const cap = this.capitalsManager.capitalsData[iso3];
    return cap ? { lat: cap.lat, lon: cap.lon } : null;
  }

  clear() {
    if (this.tradeEntities) {
      this.tradeEntities.forEach(entity => this.viewer.entities.remove(entity));
      this.tradeEntities = [];
    }
    this.activeIso3 = null;
    const tp = document.getElementById('tradePanel');
    if (tp) tp.classList.remove('visible');
  }

  _fillLeftPanel(data) {
    document.getElementById('tradeCountryName').textContent = data.name;
    document.getElementById('tradeTotalExports').textContent = `$${data.total_exports} млрд`;
    document.getElementById('tradeTotalImports').textContent = `$${data.total_imports} млрд`;
    
    const balanceEl = document.getElementById('tradeBalance');
    if (data.balance > 0) {
      balanceEl.textContent = `+$${data.balance} млрд (профицит)`;
      balanceEl.style.color = '#4caf50';
    } else if (data.balance < 0) {
      balanceEl.textContent = `-$${Math.abs(data.balance)} млрд (дефицит)`;
      balanceEl.style.color = '#f44336';
    } else {
      balanceEl.textContent = 'Сбалансирован';
      balanceEl.style.color = '#ffc107';
    }

    // Топ-5 партнёров по обороту
    const partnersDiv = document.getElementById('tradeTopPartners');
    partnersDiv.innerHTML = '';
    if (data.partners) {
      data.partners.forEach(partner => {
        const total = partner.export + partner.import;
        const div = document.createElement('div');
        div.className = 'trade-item';
        div.innerHTML = `<span>${partner.name}</span><span>$${total} млрд</span>`;
        partnersDiv.appendChild(div);
      });
    }

    // Экспорт
    const exportList = document.getElementById('tradeTopExports');
    exportList.innerHTML = '';
    data.top_exports.forEach(item => {
      const div = document.createElement('div');
      div.className = 'trade-item';
      div.innerHTML = `<span>${item.category}</span><span style="color:#4caf50">$${item.value} млрд</span>`;
      exportList.appendChild(div);
    });

    // Импорт
    const importList = document.getElementById('tradeTopImports');
    importList.innerHTML = '';
    data.top_imports.forEach(item => {
      const div = document.createElement('div');
      div.className = 'trade-item';
      div.innerHTML = `<span>${item.category}</span><span style="color:#f44336">$${item.value} млрд</span>`;
      importList.appendChild(div);
    });

    document.getElementById('tradePanel').classList.add('visible');
  }
}