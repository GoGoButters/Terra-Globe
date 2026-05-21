class DataStore {
  constructor() {
    this.countries = {};
    this.nameToIso3 = {};
    this.isReady = false;
  }

  async load() {
    try {
      // Fetch GeoJSON from API instead of static file
      const geojson = await API.getCountriesGeoJSON();
      if (!geojson || geojson.type !== 'FeatureCollection' || !Array.isArray(geojson.features)) {
        console.error('❌ Invalid GeoJSON response from API');
        return;
      }
      console.log('🗺️ Загружено границ стран:', geojson.features.length);

      // Fetch all countries with their latest indicators
      const countriesList = await API.getCountries();
      if (!Array.isArray(countriesList)) {
        console.error('❌ Invalid countries response from API');
        return;
      }
      console.log('📊 Загружено стран с показателями:', countriesList.length);

      let matched = 0;
      let unmatched = 0;

      geojson.features.forEach(feature => {
        const iso3 = this.extractISO3(feature.properties);
        if (!iso3) {
          unmatched++;
          return;
        }

        // Find country data from API response
        const countryData = countriesList.find(c => c.iso3 === iso3);

        this.countries[iso3] = {
          iso3: iso3,
          name: countryData ? countryData.name : (feature.properties.name || ''),
          geometry: feature.geometry,
          // Additional data will be fetched on-demand via API.getCountry(iso3)
        };

        if (countryData) {
          this.countries[iso3].capital_name = countryData.capital_name;
          this.countries[iso3].capital_lat = countryData.capital_lat;
          this.countries[iso3].capital_lon = countryData.capital_lon;
        }

        matched++;
      });

      console.log('✅ Объединено стран (показатели + границы):', matched);
      console.log('ℹ️ Пропущено (нет подходящего кода):', unmatched);
      this.isReady = true;
    } catch (e) {
      console.error('❌ Ошибка загрузки данных:', e);
    }
  }

  /**
   * Fetch full country data including indicators from API.
   * Used when clicking on a country.
   */
  async fetchCountryData(iso3) {
    try {
      const data = await API.getCountry(iso3);
      // Merge with existing country data
      if (this.countries[iso3]) {
        this.countries[iso3] = { ...this.countries[iso3], ...data };
      } else {
        this.countries[iso3] = data;
      }
      return this.countries[iso3];
    } catch (e) {
      console.error(`❌ Error fetching country ${iso3}:`, e);
      return null;
    }
  }

  /**
   * Extracts three-letter ISO3 code from GeoJSON properties.
   */
  extractISO3(props) {
    const code = props['ISO3166-1-Alpha-3'] ||
                 props.ISO_A3 ||
                 props.ADM0_A3 ||
                 props.iso3;

    if (code && code !== '-99') {
      return code;
    }

    return null;
  }

  get(iso3) { return this.countries[iso3] || null; }
  getAllCodes() { return Object.keys(this.countries); }
}
