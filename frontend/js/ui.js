function setupUI(viewer, layerManager, countryCard, capitalsManager, tradeManager, diplomacyManager) {
  let activeMode = null;
  let compareMode = false;
  let firstCountryData = null;
  let secondCountryData = null;

  const leftPanel = document.getElementById('leftPanel');
  const rightComparePanel = document.getElementById('rightComparePanel');
  const layersPanel = document.getElementById('layersPanel');
  const layersContent = document.getElementById('layersContent');
  const layerCard = document.getElementById('layerCard');
  const alliancesPanel = document.getElementById('alliancesPanel');
  const allianceCard = document.getElementById('allianceCard');
  const tradePanel = document.getElementById('tradePanel');
  const diplomacyPanel = document.getElementById('diplomacyPanel');
  const layersToggle = document.getElementById('layersToggle');
  const compareToggle = document.getElementById('compareToggle');
  const alliancesToggle = document.getElementById('alliancesToggle');
  const tradeToggle = document.getElementById('tradeToggle');
  const diplomacyToggle = document.getElementById('diplomacyToggle');
  const alliancesList = document.getElementById('alliancesList');

  const compareName = document.getElementById('compareCountryName');
  const compareIncome = document.getElementById('compareIncome');
  const compareGdp = document.getElementById('compareGdp');
  const compareGdpPerCapita = document.getElementById('compareGdpPerCapita');
  const compareInflation = document.getElementById('compareInflation');
  const compareGini = document.getElementById('compareGini');
  const compareUnemployment = document.getElementById('compareUnemployment');
  const comparePop = document.getElementById('comparePopulation');
  const compareHdi = document.getElementById('compareHdi');
  const compareLifeExpectancy = document.getElementById('compareLifeExpectancy');
  const compareLiteracy = document.getElementById('compareLiteracy');
  const comparePopulationDensity = document.getElementById('comparePopulationDensity');
  const compareUrbanization = document.getElementById('compareUrbanization');
  const compareFreedom = document.getElementById('compareFreedom');
  const compareDemocracyIndex = document.getElementById('compareDemocracyIndex');
  const compareCorruption = document.getElementById('compareCorruption');
  const comparePressFreedom = document.getElementById('comparePressFreedom');
  const comparePoliticalStability = document.getElementById('comparePoliticalStability');
  const compareMilitaryPower = document.getElementById('compareMilitaryPower');
  const compareMilitaryBudget = document.getElementById('compareMilitaryBudget');
  const compareNuclearWeapons = document.getElementById('compareNuclearWeapons');

  // Helper to get value from country data (flat or API nested format)
  function _val(data, field) {
    if (!data) return null;
    if (data[field] !== undefined) return data[field];
    if (data.indicators && data.indicators[field] !== undefined) return data.indicators[field];
    return null;
  }

  function resetModes() {
    layersPanel.classList.remove('visible');
    layerCard.classList.remove('visible');
    alliancesPanel.classList.remove('visible');
    allianceCard.classList.remove('visible');
    rightComparePanel.classList.remove('visible');
    tradePanel.classList.remove('visible');
    diplomacyPanel.classList.remove('visible');
    layersToggle.classList.remove('active');
    alliancesToggle.classList.remove('active');
    compareToggle.classList.remove('active');
    tradeToggle.classList.remove('active');
    diplomacyToggle.classList.remove('active');
    layerManager.setAllianceMode(false);
    layerManager.setDataVisible(false);
    countryCard.hide();
    layerManager.clearHighlight();
    tradeManager.clear();
    diplomacyManager.clear();
    compareMode = false;
    firstCountryData = null;
    secondCountryData = null;
    activeMode = null;
    layerManager.switchLayer('income');
  }

  // --- Слои ---
  async function enableLayersMode() {
    if (activeMode === 'layers') { resetModes(); return; }
    resetModes();
    if (!layerManager.layersData || layerManager.layersData.length === 0) {
      await layerManager.loadLayersData();
      buildLayersUI();
    }
    layerManager.setDataVisible(true);
    layersPanel.classList.add('visible');
    layerCard.classList.add('visible');
    layersToggle.classList.add('active');
    activeMode = 'layers';
    const activeLayer = layerManager.layersData.find(l => l.code === layerManager.currentLayer);
    if (activeLayer) showLayerCard(activeLayer);
  }

  function buildLayersUI() {
    const categories = {
      economy: { title: '💰 Экономика', layers: [] },
      society: { title: '👥 Социум', layers: [] },
      politics: { title: '🗽 Политика', layers: [] },
      military: { title: '⚔️ Военные', layers: [] }
    };

    // layersData is now an array from API
    const layersArray = Array.isArray(layerManager.layersData)
      ? layerManager.layersData
      : Object.entries(layerManager.layersData).map(([key, layer]) => ({ key, ...layer }));

    layersArray.forEach(layer => {
      const key = layer.code || layer.key;
      if (!key) return; // Skip layers without identifier
      const cat = categories[layer.category];
      if (cat) {
        cat.layers.push({ key, ...layer });
      }
    });

    layersContent.innerHTML = '';
    Object.values(categories).forEach(cat => {
      if (!cat.layers.length) return;
      const div = document.createElement('div');
      div.className = 'layers-category';
      const title = document.createElement('h4');
      title.className = 'layers-cat-title';
      title.textContent = cat.title;
      div.appendChild(title);

      cat.layers.forEach(layer => {
        const label = document.createElement('label');
        label.className = 'layer-radio-label';
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'layer';
        radio.value = layer.key;
        if (layer.key === layerManager.currentLayer) radio.checked = true;
        radio.addEventListener('change', () => {
          layerManager.switchLayer(layer.key);
          showLayerCard(layer);
        });
        label.appendChild(radio);
        label.appendChild(document.createTextNode(layer.name));
        div.appendChild(label);
      });

      layersContent.appendChild(div);
    });
  }

  function showLayerCard(layer) {
    document.getElementById('layerCardName').textContent = layer.name;
    document.getElementById('layerDesc').textContent = layer.description || '—';
    document.getElementById('layerMethod').textContent = layer.methodology || '—';
    document.getElementById('layerSource').textContent = layer.source || '—';
    const urlEl = document.getElementById('layerSourceUrl');
    if (layer.source_url) {
      urlEl.href = layer.source_url;
      urlEl.style.display = 'inline-block';
    } else {
      urlEl.style.display = 'none';
    }

    const legendDiv = document.getElementById('layerLegend');
    legendDiv.innerHTML = '';
    if (layer.display_type === 'categorical' && layer.categories) {
      layer.categories.forEach(cat => {
        const item = document.createElement('div');
        item.className = 'legend-item';
        const color = document.createElement('span');
        color.className = 'legend-color';
        color.style.background = cat.color;
        const label = document.createElement('span');
        label.className = 'legend-label';
        label.textContent = cat.label;
        item.appendChild(color);
        item.appendChild(label);
        legendDiv.appendChild(item);
      });
    } else if (layer.display_type === 'gradient' && layer.gradient_stops && layer.gradient_stops.length > 0) {
      const gradientDiv = document.createElement('div');
      gradientDiv.style.cssText = `height:14px;border-radius:3px;background:linear-gradient(to right,${layer.gradient_stops.map(s => s.color).join(',')});margin-bottom:6px;`;
      legendDiv.appendChild(gradientDiv);
      const labelsDiv = document.createElement('div');
      labelsDiv.style.cssText = 'display:flex;justify-content:space-between;font-size:11px;color:rgba(255,255,255,0.6);';
      labelsDiv.innerHTML = `<span>${layer.gradient_stops[0].label}</span><span>${layer.gradient_stops[layer.gradient_stops.length-1].label}</span>`;
      legendDiv.appendChild(labelsDiv);
    }
  }

  // --- Сравнение ---
  function enableCompareMode() {
    if (activeMode === 'compare') { resetModes(); return; }
    resetModes();
    compareMode = true;
    compareToggle.classList.add('active');
    activeMode = 'compare';
    leftPanel.classList.add('visible');
  }

  // --- Альянсы ---
  async function enableAlliancesMode() {
    if (activeMode === 'alliances') { resetModes(); return; }
    resetModes();
    if (Object.keys(layerManager.allianceData).length === 0) {
      await layerManager.loadAlliances();
      buildAlliancesUI();
    }
    layerManager.setAllianceMode(true);
    alliancesPanel.classList.add('visible');
    alliancesToggle.classList.add('active');
    activeMode = 'alliances';
  }

  function buildAlliancesUI() {
    alliancesList.innerHTML = '';
    Object.entries(layerManager.allianceData).forEach(([key, data]) => {
      const label = document.createElement('label');
      label.className = 'alliance-checkbox';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = key;
      const colorBox = document.createElement('span');
      colorBox.className = 'alliance-color';
      colorBox.style.background = data.color;
      const text = document.createElement('span');
      text.className = 'alliance-label';
      text.textContent = data.name;
      label.appendChild(checkbox);
      label.appendChild(colorBox);
      label.appendChild(text);
      checkbox.addEventListener('change', function() {
        layerManager.toggleAlliance(key, this.checked);
        if (this.checked) showAllianceCard(data);
        else {
          const anyActive = Object.values(layerManager.activeAlliances).some(v => v);
          if (!anyActive) allianceCard.classList.remove('visible');
        }
      });
      alliancesList.appendChild(label);
    });
  }

  function showAllianceCard(data) {
    document.getElementById('allianceCardName').textContent = data.name;
    document.getElementById('acFounded').textContent = data.founded || '—';
    document.getElementById('acHQ').textContent = data.headquarters || '—';
    document.getElementById('acCount').textContent = data.members.length;
    document.getElementById('acInfo').textContent = data.info || '—';
    const featuresList = document.getElementById('acFeatures');
    featuresList.innerHTML = '';
    (data.features || []).forEach(f => { const li = document.createElement('li'); li.textContent = f; featuresList.appendChild(li); });
    const membersDiv = document.getElementById('acMembers');
    membersDiv.innerHTML = '';
    data.members.forEach(iso3 => {
      const tag = document.createElement('span');
      tag.className = 'member-tag';
      const country = layerManager.dataStore.get(iso3);
      tag.textContent = country ? country.name : iso3;
      membersDiv.appendChild(tag);
    });
    allianceCard.classList.add('visible');
  }

  // --- Торговля ---
  async function enableTradeMode() {
    if (activeMode === 'trade') { resetModes(); return; }
    resetModes();
    tradeToggle.classList.add('active');
    tradePanel.classList.add('visible');
    activeMode = 'trade';
  }

  // --- Дипломатия ---
  async function enableDiplomacyMode() {
    if (activeMode === 'diplomacy') { resetModes(); return; }
    resetModes();
    diplomacyToggle.classList.add('active');
    diplomacyPanel.classList.add('visible');
    activeMode = 'diplomacy';
    firstCountryData = null;
    secondCountryData = null;
  }

  // --- Клик по глобусу ---
  const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction(async function(click) {
    try {
      if (activeMode === 'alliances' || activeMode === 'layers') return;
      const picked = viewer.scene.pick(click.position);
      if (!Cesium.defined(picked) || !picked.id || !picked.id._customData) {
        if (!compareMode) { countryCard.hide(); layerManager.clearHighlight(); }
        return;
      }
      const entityData = picked.id._customData;

      // Fetch full country data from API
      const countryData = await layerManager.dataStore.fetchCountryData(entityData.iso3);
      const data = countryData || entityData;

      if (activeMode === 'trade') {
        tradeManager.showTrade(data.iso3);
        return;
      }

      if (activeMode === 'diplomacy') {
        if (!firstCountryData) {
          firstCountryData = data;
          countryCard.show(data);
          layerManager.highlight(data.iso3);
          console.log('🤝 Первая страна:', data.name);
        } else if (!secondCountryData && data.iso3 !== firstCountryData.iso3) {
          secondCountryData = data;
          console.log('🤝 Вторая страна:', data.name);
          diplomacyManager.showRelations(firstCountryData.iso3, secondCountryData.iso3);
        } else {
          firstCountryData = data;
          secondCountryData = null;
          countryCard.show(data);
          layerManager.highlight(data.iso3);
          diplomacyPanel.classList.remove('visible');
        }
        return;
      }

      if (compareMode) {
        if (!firstCountryData) {
          firstCountryData = data;
          countryCard.show(data);
          layerManager.highlight(data.iso3);
          rightComparePanel.classList.add('visible');
          const hint = leftPanel.querySelector('.panel-hint');
          if (hint) hint.textContent = 'Выберите вторую страну';
        } else if (!secondCountryData) {
          if (data.iso3 === firstCountryData.iso3) return;
          secondCountryData = data;
          showCompareCountry(data);
          countryCard.applyComparison(firstCountryData, secondCountryData);
          applyCompareComparison(firstCountryData, secondCountryData);
          const hint = rightComparePanel.querySelector('.panel-hint');
          if (hint) hint.textContent = 'Сравнение активно';
        } else {
          if (data.iso3 === firstCountryData.iso3 || data.iso3 === secondCountryData.iso3) return;
          const oldFirst = firstCountryData;
          firstCountryData = data;
          secondCountryData = oldFirst;
          countryCard.show(firstCountryData);
          showCompareCountry(secondCountryData);
          countryCard.applyComparison(firstCountryData, secondCountryData);
          applyCompareComparison(firstCountryData, secondCountryData);
          layerManager.clearHighlight();
          layerManager.highlight(firstCountryData.iso3);
        }
      } else {
        countryCard.show(data);
        layerManager.highlight(data.iso3);
        leftPanel.classList.add('visible');
      }
    } catch (err) {
      console.error('❌ Error handling globe click:', err);
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  function showCompareCountry(data) {
    compareName.textContent = data.name || '—';
    const im = { high: 'Высокий', 'upper-middle': 'Выше среднего', 'lower-middle': 'Ниже среднего', low: 'Низкий' };
    const income = _val(data, 'income');
    compareIncome.textContent = im[String(income).toLowerCase()] || income || '—';

    const gdp = _val(data, 'gdp');
    compareGdp.textContent = gdp != null ? `${gdp} млрд $` : '—';
    const gdpPerCapita = _val(data, 'gdp_per_capita');
    compareGdpPerCapita.textContent = gdpPerCapita != null ? `${gdpPerCapita} $` : '—';
    const inflation = _val(data, 'inflation');
    compareInflation.textContent = inflation != null ? `${inflation}%` : '—';
    const gini = _val(data, 'gini');
    compareGini.textContent = gini != null ? gini : '—';
    const unemployment = _val(data, 'unemployment');
    compareUnemployment.textContent = unemployment != null ? `${unemployment}%` : '—';
    const pop = _val(data, 'pop');
    comparePop.textContent = pop != null ? `${pop} млн` : '—';
    const hdi = _val(data, 'hdi');
    compareHdi.textContent = hdi != null ? hdi : '—';
    const lifeExpectancy = _val(data, 'life_expectancy');
    compareLifeExpectancy.textContent = lifeExpectancy != null ? `${lifeExpectancy} лет` : '—';
    const literacy = _val(data, 'literacy');
    compareLiteracy.textContent = literacy != null ? `${literacy}%` : '—';
    const populationDensity = _val(data, 'population_density');
    comparePopulationDensity.textContent = populationDensity != null ? `${populationDensity} чел/км²` : '—';
    const urbanization = _val(data, 'urbanization');
    compareUrbanization.textContent = urbanization != null ? `${urbanization}%` : '—';
    const freedom = _val(data, 'freedom');
    compareFreedom.textContent = freedom != null ? `${freedom}/100` : '—';
    const democracyIndex = _val(data, 'democracy_index');
    compareDemocracyIndex.textContent = democracyIndex != null ? democracyIndex : '—';
    const corruption = _val(data, 'corruption');
    compareCorruption.textContent = corruption != null ? corruption : '—';
    const pressFreedom = _val(data, 'press_freedom');
    comparePressFreedom.textContent = pressFreedom != null ? pressFreedom : '—';
    const politicalStability = _val(data, 'political_stability');
    comparePoliticalStability.textContent = politicalStability != null ? politicalStability : '—';
    const militaryPower = _val(data, 'military_power');
    compareMilitaryPower.textContent = militaryPower != null ? militaryPower : '—';
    const militaryBudget = _val(data, 'military_budget');
    compareMilitaryBudget.textContent = militaryBudget != null ? `${militaryBudget}% ВВП` : '—';
    const nuclearWeapons = _val(data, 'nuclear_weapons');
    compareNuclearWeapons.textContent = (nuclearWeapons != null && nuclearWeapons > 0) ? 'Да' : 'Нет';
  }

  function applyCompareComparison(first, second) {
    const fields = [
      { el: compareGdp, v: _val(first, 'gdp'), ov: _val(second, 'gdp'), hi: true },
      { el: compareGdpPerCapita, v: _val(first, 'gdp_per_capita'), ov: _val(second, 'gdp_per_capita'), hi: true },
      { el: compareInflation, v: _val(first, 'inflation'), ov: _val(second, 'inflation'), hi: false },
      { el: compareGini, v: _val(first, 'gini'), ov: _val(second, 'gini'), hi: false },
      { el: compareUnemployment, v: _val(first, 'unemployment'), ov: _val(second, 'unemployment'), hi: false },
      { el: compareHdi, v: _val(first, 'hdi'), ov: _val(second, 'hdi'), hi: true },
      { el: compareLifeExpectancy, v: _val(first, 'life_expectancy'), ov: _val(second, 'life_expectancy'), hi: true },
      { el: compareLiteracy, v: _val(first, 'literacy'), ov: _val(second, 'literacy'), hi: true },
      { el: comparePopulationDensity, v: _val(first, 'population_density'), ov: _val(second, 'population_density'), hi: false },
      { el: compareUrbanization, v: _val(first, 'urbanization'), ov: _val(second, 'urbanization'), hi: true },
      { el: compareFreedom, v: _val(first, 'freedom'), ov: _val(second, 'freedom'), hi: true },
      { el: compareDemocracyIndex, v: _val(first, 'democracy_index'), ov: _val(second, 'democracy_index'), hi: true },
      { el: compareCorruption, v: _val(first, 'corruption'), ov: _val(second, 'corruption'), hi: true },
      { el: comparePressFreedom, v: _val(first, 'press_freedom'), ov: _val(second, 'press_freedom'), hi: false },
      { el: comparePoliticalStability, v: _val(first, 'political_stability'), ov: _val(second, 'political_stability'), hi: true },
      { el: compareMilitaryPower, v: _val(first, 'military_power'), ov: _val(second, 'military_power'), hi: false },
      { el: compareMilitaryBudget, v: _val(first, 'military_budget'), ov: _val(second, 'military_budget'), hi: false },
      { el: comparePop, v: _val(first, 'pop'), ov: _val(second, 'pop'), hi: false }
    ];

    fields.forEach(({ el, v, ov, hi }) => {
      if (v === null || v === undefined || ov === null || ov === undefined) {
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

  // --- Кнопки ---
  layersToggle.addEventListener('click', enableLayersMode);
  compareToggle.addEventListener('click', enableCompareMode);
  alliancesToggle.addEventListener('click', enableAlliancesMode);
  tradeToggle.addEventListener('click', enableTradeMode);
  diplomacyToggle.addEventListener('click', enableDiplomacyMode);

  // --- Чекбокс столиц ---
  document.getElementById('showCapitals').addEventListener('change', function() {
    capitalsManager.setVisible(this.checked);
  });
}
