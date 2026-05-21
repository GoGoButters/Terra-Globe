class CountryCard {
  constructor() {
    this.panel = document.getElementById('leftPanel');
    this.nameEl = document.getElementById('countryName');
    this.incomeEl = document.getElementById('countryIncome');
    this.gdpEl = document.getElementById('countryGdp');
    this.gdpPerCapitaEl = document.getElementById('countryGdpPerCapita');
    this.inflationEl = document.getElementById('countryInflation');
    this.giniEl = document.getElementById('countryGini');
    this.unemploymentEl = document.getElementById('countryUnemployment');
    this.popEl = document.getElementById('countryPopulation');
    this.hdiEl = document.getElementById('countryHdi');
    this.lifeExpectancyEl = document.getElementById('countryLifeExpectancy');
    this.literacyEl = document.getElementById('countryLiteracy');
    this.populationDensityEl = document.getElementById('countryPopulationDensity');
    this.urbanizationEl = document.getElementById('countryUrbanization');
    this.freeEl = document.getElementById('countryFreedom');
    this.democracyIndexEl = document.getElementById('countryDemocracyIndex');
    this.corruptionEl = document.getElementById('countryCorruption');
    this.pressFreedomEl = document.getElementById('countryPressFreedom');
    this.politicalStabilityEl = document.getElementById('countryPoliticalStability');
    this.militaryPowerEl = document.getElementById('countryMilitaryPower');
    this.militaryBudgetEl = document.getElementById('countryMilitaryBudget');
    this.nuclearWeaponsEl = document.getElementById('countryNuclearWeapons');

    // Сохраняем ссылки на все элементы для очистки классов
    this._allElements = [
      this.incomeEl, this.gdpEl, this.gdpPerCapitaEl, this.inflationEl,
      this.giniEl, this.unemploymentEl, this.popEl, this.hdiEl,
      this.lifeExpectancyEl, this.literacyEl, this.populationDensityEl,
      this.urbanizationEl, this.freeEl, this.democracyIndexEl,
      this.corruptionEl, this.pressFreedomEl, this.politicalStabilityEl,
      this.militaryPowerEl, this.militaryBudgetEl, this.nuclearWeaponsEl
    ];
  }

  /**
   * Get a value from country data, supporting both flat and API (nested indicators) formats.
   */
  _val(data, field) {
    if (data[field] !== undefined) return data[field];
    if (data.indicators && data.indicators[field] !== undefined) return data.indicators[field];
    return null;
  }

  show(data) {
    this.nameEl.textContent = data.name || '—';

    const incomeMap = { 'high': 'Высокий', 'upper-middle': 'Выше среднего', 'lower-middle': 'Ниже среднего', 'low': 'Низкий' };
    const income = this._val(data, 'income');
    this.incomeEl.textContent = incomeMap[String(income).toLowerCase()] || income || '—';

    const gdp = this._val(data, 'gdp');
    this.gdpEl.textContent = gdp != null ? `${gdp} млрд $` : '—';

    const gdpPerCapita = this._val(data, 'gdp_per_capita');
    this.gdpPerCapitaEl.textContent = gdpPerCapita != null ? `${gdpPerCapita} $` : '—';

    const inflation = this._val(data, 'inflation');
    this.inflationEl.textContent = inflation != null ? `${inflation}%` : '—';

    const gini = this._val(data, 'gini');
    this.giniEl.textContent = gini != null ? gini : '—';

    const unemployment = this._val(data, 'unemployment');
    this.unemploymentEl.textContent = unemployment != null ? `${unemployment}%` : '—';

    const pop = this._val(data, 'pop');
    this.popEl.textContent = pop != null ? `${pop} млн` : '—';

    const hdi = this._val(data, 'hdi');
    this.hdiEl.textContent = hdi != null ? hdi : '—';

    const lifeExpectancy = this._val(data, 'life_expectancy');
    this.lifeExpectancyEl.textContent = lifeExpectancy != null ? `${lifeExpectancy} лет` : '—';

    const literacy = this._val(data, 'literacy');
    this.literacyEl.textContent = literacy != null ? `${literacy}%` : '—';

    const populationDensity = this._val(data, 'population_density');
    this.populationDensityEl.textContent = populationDensity != null ? `${populationDensity} чел/км²` : '—';

    const urbanization = this._val(data, 'urbanization');
    this.urbanizationEl.textContent = urbanization != null ? `${urbanization}%` : '—';

    const freedom = this._val(data, 'freedom');
    this.freeEl.textContent = freedom != null ? `${freedom}/100` : '—';

    const democracyIndex = this._val(data, 'democracy_index');
    this.democracyIndexEl.textContent = democracyIndex != null ? democracyIndex : '—';

    const corruption = this._val(data, 'corruption');
    this.corruptionEl.textContent = corruption != null ? corruption : '—';

    const pressFreedom = this._val(data, 'press_freedom');
    this.pressFreedomEl.textContent = pressFreedom != null ? pressFreedom : '—';

    const politicalStability = this._val(data, 'political_stability');
    this.politicalStabilityEl.textContent = politicalStability != null ? politicalStability : '—';

    const militaryPower = this._val(data, 'military_power');
    this.militaryPowerEl.textContent = militaryPower != null ? militaryPower : '—';

    const militaryBudget = this._val(data, 'military_budget');
    this.militaryBudgetEl.textContent = militaryBudget != null ? `${militaryBudget}% ВВП` : '—';

    const nuclearWeapons = this._val(data, 'nuclear_weapons');
    this.nuclearWeaponsEl.textContent = (nuclearWeapons != null && nuclearWeapons > 0) ? 'Да' : 'Нет';

    this._clearComparisonClasses();
    this.panel.classList.add('visible');
  }

  hide() {
    this.panel.classList.remove('visible');
    this._clearComparisonClasses();
  }

  /**
   * Применяет стили сравнения к левой панели.
   * @param {Object} leftData  — данные первой страны
   * @param {Object} rightData — данные второй страны
   */
  applyComparison(leftData, rightData) {
    const fields = [
      { el: this.gdpEl, v: this._val(leftData, 'gdp'), ov: this._val(rightData, 'gdp'), hi: true },
      { el: this.gdpPerCapitaEl, v: this._val(leftData, 'gdp_per_capita'), ov: this._val(rightData, 'gdp_per_capita'), hi: true },
      { el: this.inflationEl, v: this._val(leftData, 'inflation'), ov: this._val(rightData, 'inflation'), hi: false },
      { el: this.giniEl, v: this._val(leftData, 'gini'), ov: this._val(rightData, 'gini'), hi: false },
      { el: this.unemploymentEl, v: this._val(leftData, 'unemployment'), ov: this._val(rightData, 'unemployment'), hi: false },
      { el: this.hdiEl, v: this._val(leftData, 'hdi'), ov: this._val(rightData, 'hdi'), hi: true },
      { el: this.lifeExpectancyEl, v: this._val(leftData, 'life_expectancy'), ov: this._val(rightData, 'life_expectancy'), hi: true },
      { el: this.literacyEl, v: this._val(leftData, 'literacy'), ov: this._val(rightData, 'literacy'), hi: true },
      { el: this.populationDensityEl, v: this._val(leftData, 'population_density'), ov: this._val(rightData, 'population_density'), hi: false },
      { el: this.urbanizationEl, v: this._val(leftData, 'urbanization'), ov: this._val(rightData, 'urbanization'), hi: true },
      { el: this.freeEl, v: this._val(leftData, 'freedom'), ov: this._val(rightData, 'freedom'), hi: true },
      { el: this.democracyIndexEl, v: this._val(leftData, 'democracy_index'), ov: this._val(rightData, 'democracy_index'), hi: true },
      { el: this.corruptionEl, v: this._val(leftData, 'corruption'), ov: this._val(rightData, 'corruption'), hi: true },
      { el: this.pressFreedomEl, v: this._val(leftData, 'press_freedom'), ov: this._val(rightData, 'press_freedom'), hi: false },
      { el: this.politicalStabilityEl, v: this._val(leftData, 'political_stability'), ov: this._val(rightData, 'political_stability'), hi: true },
      { el: this.militaryPowerEl, v: this._val(leftData, 'military_power'), ov: this._val(rightData, 'military_power'), hi: false },
      { el: this.militaryBudgetEl, v: this._val(leftData, 'military_budget'), ov: this._val(rightData, 'military_budget'), hi: false },
      { el: this.popEl, v: this._val(leftData, 'pop'), ov: this._val(rightData, 'pop'), hi: false }
    ];

    fields.forEach(({ el, v, ov, hi }) => {
      if (!el) return;
      if (v === null || ov === null) {
        el.className = 'info-value';
      } else if (v === ov) {
        el.className = 'info-value equal';
      } else if ((hi && v > ov) || (!hi && v < ov)) {
        el.className = 'info-value better arrow-up';
      } else {
        el.className = 'info-value worse arrow-down';
      }
    });
  }

  _clearComparisonClasses() {
    this._allElements.forEach(el => {
      if (el) el.className = 'info-value';
    });
  }
}