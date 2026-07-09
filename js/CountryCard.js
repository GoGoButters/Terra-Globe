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

  show(data) {
    this.nameEl.textContent = data.name || '—';

    const incomeMap = { 'high': 'Высокий', 'upper-middle': 'Выше среднего', 'lower-middle': 'Ниже среднего', 'low': 'Низкий' };
    this.incomeEl.textContent = incomeMap[data.income] || data.income || '—';
    this.gdpEl.textContent = data.gdp ? `${data.gdp} млрд $` : '—';
    this.gdpPerCapitaEl.textContent = data.gdp_per_capita ? `${data.gdp_per_capita} $` : '—';
    this.inflationEl.textContent = data.inflation ? `${data.inflation}%` : '—';
    this.giniEl.textContent = data.gini || '—';
    this.unemploymentEl.textContent = data.unemployment ? `${data.unemployment}%` : '—';
    this.popEl.textContent = data.pop ? `${data.pop} млн` : '—';
    this.hdiEl.textContent = data.hdi || '—';
    this.lifeExpectancyEl.textContent = data.life_expectancy ? `${data.life_expectancy} лет` : '—';
    this.literacyEl.textContent = data.literacy ? `${data.literacy}%` : '—';
    this.populationDensityEl.textContent = data.population_density ? `${data.population_density} чел/км²` : '—';
    this.urbanizationEl.textContent = data.urbanization ? `${data.urbanization}%` : '—';
    this.freeEl.textContent = data.freedom ? `${data.freedom}/100` : '—';
    this.democracyIndexEl.textContent = data.democracy_index || '—';
    this.corruptionEl.textContent = data.corruption || '—';
    this.pressFreedomEl.textContent = data.press_freedom || '—';
    this.politicalStabilityEl.textContent = data.political_stability || '—';
    this.militaryPowerEl.textContent = data.military_power || '—';
    this.militaryBudgetEl.textContent = data.military_budget ? `${data.military_budget}% ВВП` : '—';
    this.nuclearWeaponsEl.textContent = data.nuclear_weapons === 1 ? 'Да' : 'Нет';

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
      { el: this.gdpEl, v: leftData.gdp, ov: rightData.gdp, hi: true },
      { el: this.gdpPerCapitaEl, v: leftData.gdp_per_capita, ov: rightData.gdp_per_capita, hi: true },
      { el: this.inflationEl, v: leftData.inflation, ov: rightData.inflation, hi: false },
      { el: this.giniEl, v: leftData.gini, ov: rightData.gini, hi: false },
      { el: this.unemploymentEl, v: leftData.unemployment, ov: rightData.unemployment, hi: false },
      { el: this.hdiEl, v: leftData.hdi, ov: rightData.hdi, hi: true },
      { el: this.lifeExpectancyEl, v: leftData.life_expectancy, ov: rightData.life_expectancy, hi: true },
      { el: this.literacyEl, v: leftData.literacy, ov: rightData.literacy, hi: true },
      { el: this.populationDensityEl, v: leftData.population_density, ov: rightData.population_density, hi: false },
      { el: this.urbanizationEl, v: leftData.urbanization, ov: rightData.urbanization, hi: true },
      { el: this.freeEl, v: leftData.freedom, ov: rightData.freedom, hi: true },
      { el: this.democracyIndexEl, v: leftData.democracy_index, ov: rightData.democracy_index, hi: true },
      { el: this.corruptionEl, v: leftData.corruption, ov: rightData.corruption, hi: true },
      { el: this.pressFreedomEl, v: leftData.press_freedom, ov: rightData.press_freedom, hi: false },
      { el: this.politicalStabilityEl, v: leftData.political_stability, ov: rightData.political_stability, hi: true },
      { el: this.militaryPowerEl, v: leftData.military_power, ov: rightData.military_power, hi: false },
      { el: this.militaryBudgetEl, v: leftData.military_budget, ov: rightData.military_budget, hi: false },
      { el: this.popEl, v: leftData.pop, ov: rightData.pop, hi: false }
    ];

    fields.forEach(({ el, v, ov, hi }) => {
      if (!el) return;
      if (v === ov) {
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