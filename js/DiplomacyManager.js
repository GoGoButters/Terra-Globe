class DiplomacyManager {
  constructor(viewer, dataStore) {
    this.viewer = viewer;
    this.dataStore = dataStore;
    this.diplomacyData = {};
    this.activePair = null;
  }

  async load() {
    try {
      const res = await fetch('data/diplomacy.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.diplomacyData = await res.json();
      console.log('🤝 Загружены дипломатические данные:', Object.keys(this.diplomacyData).length, 'пар');
    } catch (e) {
      console.error('Ошибка загрузки diplomacy.json:', e);
    }
  }

  /**
   * Показать дипломатические отношения между двумя странами.
   */
  showRelations(iso3_1, iso3_2) {
    const key1 = `${iso3_1}_${iso3_2}`;
    const key2 = `${iso3_2}_${iso3_1}`;
    const data = this.diplomacyData[key1] || this.diplomacyData[key2];

    if (!data) {
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
    const country1 = this.dataStore.get(data.country1);
    const country2 = this.dataStore.get(data.country2);
    const name1 = country1 ? country1.name : data.country1;
    const name2 = country2 ? country2.name : data.country2;

    document.getElementById('diplomacyTitle').textContent = `${name1} — ${name2}`;
    document.getElementById('diplomacySummary').textContent = data.summary;

    const docsContainer = document.getElementById('diplomacyDocs');
    docsContainer.innerHTML = '';

    data.relations.forEach(doc => {
      const card = document.createElement('div');
      card.className = 'diplomacy-doc-card';

      const header = document.createElement('div');
      header.className = 'diplomacy-doc-header';

      const title = document.createElement('h4');
      title.textContent = doc.title;

      const meta = document.createElement('span');
      meta.className = 'diplomacy-doc-meta';
      meta.textContent = `${doc.year} · ${doc.type}`;

      header.appendChild(title);
      header.appendChild(meta);

      const desc = document.createElement('p');
      desc.textContent = doc.description;

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