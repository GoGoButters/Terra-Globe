class DiplomacyManager {
  constructor(viewer, dataStore) {
    this.viewer = viewer;
    this.dataStore = dataStore;
    this.diplomacyData = {};
    this.activePair = null;
  }

  async load() {
    // Diplomacy data is now loaded on-demand via API
    this.diplomacyData = {};
    console.log('🤝 Дипломатический менеджер инициализирован (данные загружаются по запросу)');
  }

  /**
   * Показать дипломатические отношения между двумя странами.
   */
  async showRelations(iso3_1, iso3_2) {
    let data;
    try {
      data = await API.getDiplomaticRelations(iso3_1, iso3_2);
    } catch (e) {
      console.error(`❌ Error fetching diplomacy data for ${iso3_1}-${iso3_2}:`, e);
      this._showNoData(iso3_1, iso3_2);
      return;
    }

    if (!data || !data.documents || data.documents.length === 0) {
      this._showNoData(iso3_1, iso3_2);
      return;
    }

    this.activePair = data;
    this._fillPanel(data);
  }

  _showNoData(iso3_1, iso3_2) {
    const country1 = this.dataStore.get(iso3_1);
    const country2 = this.dataStore.get(iso3_2);
    const name1 = country1 ? country1.name : iso3_1;
    const name2 = country2 ? country2.name : iso3_2;

    document.getElementById('diplomacyTitle').textContent = `${name1} — ${name2}`;
    document.getElementById('diplomacySummary').textContent = 'Данные о дипломатических отношениях пока не загружены для этой пары стран.';
    document.getElementById('diplomacyDocs').innerHTML = '';
    document.getElementById('diplomacyPanel').classList.add('visible');
  }

  _fillPanel(data) {
    const name1 = data.country1_name || data.country1_iso3;
    const name2 = data.country2_name || data.country2_iso3;

    document.getElementById('diplomacyTitle').textContent = `${name1} — ${name2}`;
    document.getElementById('diplomacySummary').textContent = data.summary || '';

    const docsContainer = document.getElementById('diplomacyDocs');
    docsContainer.innerHTML = '';

    (data.documents || []).forEach(doc => {
      const card = document.createElement('div');
      card.className = 'diplomacy-doc-card';

      const header = document.createElement('div');
      header.className = 'diplomacy-doc-header';

      const title = document.createElement('h4');
      title.textContent = doc.title;

      const meta = document.createElement('span');
      meta.className = 'diplomacy-doc-meta';
      meta.textContent = [doc.year, doc.type].filter(Boolean).join(' · ');

      header.appendChild(title);
      header.appendChild(meta);

      const desc = document.createElement('p');
      desc.textContent = doc.description || '';

      card.appendChild(header);
      card.appendChild(desc);
      docsContainer.appendChild(card);
    });

    document.getElementById('diplomacyPanel').classList.add('visible');
  }

  clear() {
    this.activePair = null;
    const panel = document.getElementById('diplomacyPanel');
    if (panel) panel.classList.remove('visible');
  }
}