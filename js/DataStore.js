class DataStore {
  constructor() {
    this.countries = {};
    this.nameToIso3 = {};
    this.isReady = false;
  }

  async load() {
    try {
      const csvText = await fetch(CSV_PATH).then(r => r.text());
      const indicators = this.parseCSV(csvText);
      console.log('📊 Загружено показателей стран:', Object.keys(indicators).length);

      // Строим словарь названий для fallback-поиска
      this.nameToIso3 = {};
      for (const [iso3, data] of Object.entries(indicators)) {
        if (data.name) {
          this.nameToIso3[data.name] = iso3;
        }
      }

      const geojson = await fetch(GEOJSON_PATH).then(r => r.json());
      console.log('🗺️ Загружено границ стран:', geojson.features.length);

      let matched = 0;
      let unmatched = 0;

      geojson.features.forEach(feature => {
        const iso3 = this.extractISO3(feature.properties);
        if (!iso3) {
          unmatched++;
          return;
        }
        const data = indicators[iso3];
        if (!data) {
          unmatched++;
          return;
        }

        this.countries[iso3] = {
          ...data,
          geometry: feature.geometry
        };
        matched++;
      });

      console.log('✅ Объединено стран (показатели + границы):', matched);
      console.log('ℹ️ Пропущено (нет подходящего кода или данных):', unmatched);
      this.isReady = true;
    } catch (e) {
      console.error('❌ Ошибка загрузки данных:', e);
    }
  }

  parseCSV(text) {
    const lines = text.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim());
    const result = {};

    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim());
      if (values.length < headers.length) continue;

      const row = {};
      headers.forEach((header, idx) => { row[header] = values[idx]; });

      const iso3 = row.iso3;
      if (!iso3) continue;

      const numericFields = ['gdp', 'pop', 'hdi', 'freedom', 'gdp_per_capita', 'inflation', 'gini', 'unemployment', 'life_expectancy', 'literacy', 'population_density', 'urbanization', 'democracy_index', 'corruption', 'press_freedom', 'political_stability', 'military_power', 'military_budget', 'nuclear_weapons'];

      numericFields.forEach(field => {
        if (row[field] !== undefined) {
          row[field] = parseFloat(row[field]) || 0;
        }
      });

      result[iso3] = {
        name: row.name,
        income: row.income,
        gdp: row.gdp || 0,
        pop: row.pop || 0,
        hdi: row.hdi || 0,
        freedom: row.freedom || 0,
        gdp_per_capita: row.gdp_per_capita || 0,
        inflation: row.inflation || 0,
        gini: row.gini || 0,
        unemployment: row.unemployment || 0,
        life_expectancy: row.life_expectancy || 0,
        literacy: row.literacy || 0,
        population_density: row.population_density || 0,
        urbanization: row.urbanization || 0,
        democracy_index: row.democracy_index || 0,
        corruption: row.corruption || 0,
        press_freedom: row.press_freedom || 0,
        political_stability: row.political_stability || 0,
        military_power: row.military_power || 0,
        military_budget: row.military_budget || 0,
        nuclear_weapons: row.nuclear_weapons || 0
      };
    }
    return result;
  }

  /**
   * Извлекает трёхбуквенный ISO3-код из свойств GeoJSON-объекта.
   * Если стандартные поля отсутствуют или равны "-99", ищем по имени.
   */
  extractISO3(props) {
    // Прямые коды (основной или запасные)
    const code = props['ISO3166-1-Alpha-3'] ||
                 props.ISO_A3 ||
                 props.ADM0_A3;

    if (code && code !== '-99') {
      return code;
    }

    // Fallback: ищем по названию страны
    const name = props.name || props.ADMIN;
    if (name && this.nameToIso3[name]) {
      return this.nameToIso3[name];
    }

    return null;
  }

  get(iso3) { return this.countries[iso3] || null; }
  getAllCodes() { return Object.keys(this.countries); }
}