class CapitalsManager {
  constructor(viewer, dataStore) {
    this.viewer = viewer;
    this.dataStore = dataStore;
    this.entities = [];          // точки + метки (для совместимости)
    this._allEntities = [];      // все созданные сущности (точки и лейблы)
    this._visible = true;
    this.capitalsData = {};      // <-- НОВОЕ: хранилище данных столиц
  }

  async load() {
    try {
      const csvText = await fetch('data/capitals.csv').then(r => r.text());
      this.capitalsData = this.parseCSV(csvText);   // <-- СОХРАНЯЕМ данные
      console.log('🏛️ Загружено столиц:', Object.keys(this.capitalsData).length);

      Object.entries(this.capitalsData).forEach(([iso3, cap]) => {
        if (!this.dataStore.get(iso3)) return;
        // Validate coordinates
        if (isNaN(cap.lat) || isNaN(cap.lon)) return;

        const point = this.viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(cap.lon, cap.lat),
          point: {
            pixelSize: 5,
            color: Cesium.Color.YELLOW,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 1,
            scaleByDistance: new Cesium.NearFarScalar(1.5e6, 1.0, 1.0e7, 0.5),
            heightReference: Cesium.HeightReference.NONE,
          },
          description: `<b>${cap.name}</b><br/>Столица`,
          show: this._visible,
        });

        const label = this.viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(cap.lon, cap.lat),
          label: {
            text: cap.name,
            font: 'bold 12px "Segoe UI", sans-serif',
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 3,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -10),
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000),
          },
          show: this._visible,
        });

        this._allEntities.push(point, label);
        this.entities.push(point, label);
      });

      console.log('🏛️ Отображено столиц:', this.entities.length / 2);
    } catch (e) {
      console.error('❌ Ошибка загрузки столиц:', e);
    }
  }

  /** Показывает или скрывает все столицы. */
  setVisible(visible) {
    this._visible = visible;
    this._allEntities.forEach(entity => {
      entity.show = visible;
    });
  }

  isVisible() {
    return this._visible;
  }

  parseCSV(text) {
    const lines = text.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim());
    const result = {};

    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim());
      if (values.length < 4) continue;

      const [iso3, capital, lat, lon] = values;
      if (!iso3) continue;

      result[iso3] = {
        name: capital,
        lat: parseFloat(lat),
        lon: parseFloat(lon),
      };
    }
    return result;
  }
}