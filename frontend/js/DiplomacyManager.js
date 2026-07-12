/**
 * DiplomacyManager — full diplomatic profile panel.
 *
 * Flow:
 *   1. User clicks "Дипломатия" button → enableDiplomacyMode()
 *   2. User clicks a country on the globe → showCountryProfile(iso3)
 *   3. Fetches GET /api/diplomacy/{iso3} → Wikidata + GDELT data
 *   4. Renders: embassies list, tone cards, top partners/adversaries
 *   5. Optionally draws tone arcs on the globe
 */
class DiplomacyManager {
  constructor(viewer, dataStore, capitalsManager) {
    this.viewer = viewer;
    this.dataStore = dataStore;
    this.capitalsManager = capitalsManager;
    this.activeIso3 = null;
    this.diplomacyEntities = [];
  }

  async load() {
    console.log('🤝 DiplomacyManager инициализирован (данные загружаются по запросу)');
  }

  // ─────────────────────────────────────────────────────
  // Show full diplomatic profile for a single country
  // ─────────────────────────────────────────────────────
  async showCountryProfile(iso3) {
    this.clear();
    this.activeIso3 = iso3;

    const countryData = this.dataStore.get(iso3) || await this.dataStore.fetchCountryData(iso3);
    const displayName = countryData?.name_ru || countryData?.name || iso3;

    // Update panel title
    document.getElementById('diplomacyTitle').textContent = `🤝 Дипломатия: ${displayName}`;

    // Loading state
    const summaryEl = document.getElementById('diplomacySummary');
    const docsEl = document.getElementById('diplomacyDocs');
    summaryEl.textContent = 'Загрузка дипломатических данных…';
    docsEl.innerHTML = '';

    let profile;
    try {
      profile = await API.getDiplomacyProfile(iso3);
    } catch (e) {
      console.error(`❌ Error fetching diplomacy profile for ${iso3}:`, e);
      summaryEl.textContent = '⚠️ Не удалось загрузить дипломатические данные.';
      return;
    }

    this._renderProfile(profile, countryData);
    document.getElementById('diplomacyPanel').classList.add('visible');
  }

  // ─────────────────────────────────────────────────────
  // Show BILATERAL diplomatic relations between two countries
  // ─────────────────────────────────────────────────────
  async showBilateral(iso3_a, iso3_b) {
    this.clear();
    this.activeIso3 = iso3_a;

    const countryA = this.dataStore.get(iso3_a);
    const countryB = this.dataStore.get(iso3_b);
    const nameA = countryA?.name_ru || countryA?.name || iso3_a;
    const nameB = countryB?.name_ru || countryB?.name || iso3_b;

    // Loading state
    document.getElementById('diplomacyTitle').textContent = `🤝 ${nameA} ⟷ ${nameB}`;
    document.getElementById('diplomacySummary').textContent = 'Загрузка данных об отношениях…';
    document.getElementById('diplomacyDocs').innerHTML = '';

    let profileA, profileB, bilateral;
    try {
      [profileA, profileB, bilateral] = await Promise.all([
        API.getDiplomacyProfile(iso3_a).catch(() => null),
        API.getDiplomacyProfile(iso3_b).catch(() => null),
        API.getDiplomaticRelations(iso3_a, iso3_b).catch(() => null),
      ]);
    } catch (e) {
      console.error('❌ Error loading bilateral data:', e);
      document.getElementById('diplomacySummary').textContent = '⚠️ Не удалось загрузить данные.';
      return;
    }

    this._renderBilateralProfile(iso3_a, iso3_b, nameA, nameB, profileA, profileB, bilateral);
    document.getElementById('diplomacyPanel').classList.add('visible');
  }

  _renderBilateralProfile(iso3_a, iso3_b, nameA, nameB, profileA, profileB, bilateral) {
    const docsEl = document.getElementById('diplomacyDocs');
    docsEl.innerHTML = '';

    // ── Tone between the two ──
    let toneData = null;
    if (profileA?.tone && profileA.tone[iso3_b]) {
      toneData = profileA.tone[iso3_b];
    } else if (profileB?.tone && profileB.tone[iso3_a]) {
      toneData = profileB.tone[iso3_a];
    }

    // Summary with tone
    const summaryEl = document.getElementById('diplomacySummary');
    if (toneData) {
      const t = toneData.tone;
      const emoji = t > 3 ? '🟢' : t < -3 ? '🔴' : t < 0 ? '🟡' : '🟢';
      summaryEl.textContent = `${emoji} Тон отношений: ${t > 0 ? '+' : ''}${t.toFixed(1)} · Упоминаний: ${toneData.count} · ${toneData.trend === 'up' ? '📈' : toneData.trend === 'down' ? '📉' : '➡️'}`;
    } else {
      summaryEl.textContent = 'Данные о тоне отношений недоступны';
    }

    // ── Tone bar card ──
    if (toneData) {
      const toneCard = this._createCard();
      const t = toneData.tone;
      const barPercent = Math.min(Math.max(((t + 10) / 20) * 100, 5), 95);
      const barColor = t > 2 ? '#4caf50' : t < -2 ? '#f44336' : '#ffc107';
      toneCard.innerHTML = `
        <div class="dip-section-title">📊 Тональность упоминаний в СМИ</div>
        <div style="margin:10px 0;">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:4px;">
            <span>🔴 Враждебно (-10)</span><span>Нейтрально (0)</span><span>🟢 Дружественно (+10)</span>
          </div>
          <div style="background:linear-gradient(to right,#f44336,#ffc107,#4caf50);height:8px;border-radius:4px;position:relative;">
            <div style="position:absolute;left:${barPercent}%;top:-4px;width:12px;height:16px;background:${barColor};border:2px solid #fff;border-radius:3px;transform:translateX(-50%);"></div>
          </div>
          <div style="text-align:center;margin-top:6px;font-size:18px;font-weight:bold;color:${barColor}">${t > 0 ? '+' : ''}${t.toFixed(1)}</div>
        </div>
        <div style="display:flex;justify-content:space-around;font-size:12px;color:rgba(255,255,255,0.6);margin-top:8px;">
          <span>📰 ${toneData.count} статей</span>
          <span>📅 7 дней</span>
        </div>
      `;
      docsEl.appendChild(toneCard);
    }

    // ── Embassies (mutual) ──
    const aEmbassyInB = profileA?.embassies?.has_embassy_in?.includes(iso3_b);
    const bEmbassyInA = profileA?.embassies?.embassies_from?.includes(iso3_b);
    const embCard = this._createCard();
    embCard.innerHTML = `
      <div class="dip-section-title">🏛️ Дипломатические миссии</div>
      <div class="dip-embassy-row">
        <div class="dip-embassy-item ${aEmbassyInB ? 'dip-embassy-yes' : 'dip-embassy-no'}">
          ${aEmbassyInB ? '✅' : '❌'} Посольство ${nameA} в ${nameB}
        </div>
        <div class="dip-embassy-item ${bEmbassyInA ? 'dip-embassy-yes' : 'dip-embassy-no'}">
          ${bEmbassyInA ? '✅' : '❌'} Посольство ${nameB} в ${nameA}
        </div>
      </div>
    `;
    docsEl.appendChild(embCard);

    // ── Bilateral static data (treaties, history) ──
    if (bilateral && bilateral.summary && bilateral.summary !== 'Данные о дипломатических отношениях пока не загружены') {
      const bilCard = this._createCard();
      bilCard.innerHTML = `
        <div class="dip-section-title">📜 Исторические отношения</div>
        <p class="dip-text">${bilateral.summary}</p>
        ${(bilateral.documents || []).slice(0, 5).map(doc => `
          <div class="dip-doc-line">
            <strong>${doc.title}</strong>
            ${doc.year ? `<span class="dip-doc-year">${doc.year}</span>` : ''}
            ${doc.type ? `<span class="dip-doc-type">${doc.type}</span>` : ''}
          </div>
        `).join('')}
      `;
      docsEl.appendChild(bilCard);
    }

    // ── Articles mentioning each other ──
    if (toneData?.articles && toneData.articles.length > 0) {
      const artCard = this._createCard();
      let artHTML = '<div class="dip-section-title">📰 Свежие заголовки</div>';
      toneData.articles.slice(0, 6).forEach(a => {
        const toneColor = (a.tone || 0) > 0 ? '#4caf50' : (a.tone || 0) < 0 ? '#f44336' : '#888';
        artHTML += `
          <div class="dip-article">
            <a href="${a.url || '#'}" target="_blank" rel="noopener" class="dip-article-title">${a.title || 'Без заголовка'}</a>
            <div class="dip-article-meta">
              <span style="color:${toneColor}">Тон: ${(a.tone || 0).toFixed(1)}</span>
              ${a.date ? `<span>· ${a.date.slice(0, 10)}</span>` : ''}
            </div>
          </div>`;
      });
      artCard.innerHTML = artHTML;
      docsEl.appendChild(artCard);
    }

    // ── Draw single arc between the two capitals ──
    const capsData = this.capitalsManager?.capitalsData;
    if (capsData) {
      const capA = capsData[iso3_a];
      const capB = capsData[iso3_b];
      if (capA && capB) {
        const toneVal = toneData?.tone || 0;
        let color;
        if (toneVal > 3) color = Cesium.Color.fromCssColorString('#4caf50').withAlpha(0.8);
        else if (toneVal < -3) color = Cesium.Color.fromCssColorString('#f44336').withAlpha(0.8);
        else color = Cesium.Color.fromCssColorString('#ffc107').withAlpha(0.6);

        const path = this._computeGreatCirclePath(capA.lat, capA.lon, capB.lat, capB.lon, 80);
        const ARC_HEIGHT = 600000;
        const positions = path.map((p, i) => {
          const t = i / (path.length - 1);
          const h = ARC_HEIGHT * 4 * t * (1 - t);
          return Cesium.Cartesian3.fromDegrees(p.lon, p.lat, h);
        });

        this.diplomacyEntities.push(this.viewer.entities.add({
          polyline: {
            positions,
            width: 3,
            material: color,
            clampToGround: false,
          },
        }));

        // Label at midpoint
        const mid = path[Math.floor(path.length / 2)];
        const toneStr = `${toneVal > 0 ? '+' : ''}${toneVal.toFixed(1)}`;
        this.diplomacyEntities.push(this.viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(mid.lon, mid.lat, ARC_HEIGHT + 80000),
          label: {
            text: toneStr,
            font: 'bold 14px "Segoe UI", sans-serif',
            fillColor: color,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 4,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          },
        }));
      }
    }
  }

  // ─────────────────────────────────────────────────────
  // Legacy: show relations between two countries
  // ─────────────────────────────────────────────────────
  async showRelations(iso3_1, iso3_2) {
    // Delegate to the new single-country profile for the first country
    // and also show bilateral data in the panel
    this.clear();
    this.activeIso3 = iso3_1;

    let profile;
    try {
      profile = await API.getDiplomacyProfile(iso3_1);
    } catch (e) {
      console.error(`❌ Error fetching diplomacy for ${iso3_1}:`, e);
      this._showNoData(iso3_1, iso3_2);
      return;
    }

    // Also fetch bilateral static data
    let bilateral;
    try {
      bilateral = await API.getDiplomaticRelations(iso3_1, iso3_2);
    } catch {
      bilateral = null;
    }

    this._renderProfile(profile, null, iso3_2, bilateral);
    document.getElementById('diplomacyPanel').classList.add('visible');
  }

  // ─────────────────────────────────────────────────────
  // Render the full diplomatic profile
  // ─────────────────────────────────────────────────────
  _renderProfile(profile, countryData, highlightIso3, bilateral) {
    const iso3 = profile.iso3;
    const displayName = profile.name_ru || profile.name || iso3;
    const embassies = profile.embassies || {};
    const tone = profile.tone || {};
    const topPartners = profile.top_partners || [];
    const topAdversaries = profile.top_adversaries || [];

    // ── Title ──
    document.getElementById('diplomacyTitle').textContent = `🤝 Дипломатия: ${displayName}`;

    // ── Build panel content ──
    const docsEl = document.getElementById('diplomacyDocs');
    docsEl.innerHTML = '';

    // ── Summary / stats ──
    const summaryEl = document.getElementById('diplomacySummary');
    const embassyOut = (embassies.has_embassy_in || []).length;
    const embassyIn = (embassies.embassies_from || []).length;
    const toneCount = Object.keys(tone).length;
    summaryEl.textContent = `Посольства: ${embassyOut} за рубежом, ${embassyIn} иностранных · Партнёров с тоном: ${toneCount}`;

    // ── Bilateral detail (if two-country mode) ──
    if (highlightIso3 && bilateral) {
      const card = this._createCard();
      card.innerHTML = `
        <div class="dip-section-title">📜 Двусторонние отношения</div>
        <div class="dip-detail-line">
          <span class="dip-label">${displayName}</span>
          <span class="dip-arrow">⟷</span>
          <span class="dip-label">${this._resolveName(highlightIso3)}</span>
        </div>
        <p class="dip-text">${bilateral.summary || 'Нет данных'}</p>
      `;
      docsEl.appendChild(card);

      if (bilateral.documents && bilateral.documents.length > 0) {
        bilateral.documents.forEach(doc => {
          const docCard = this._createCard();
          docCard.innerHTML = `
            <div class="diplomacy-doc-header">
              <h4>${doc.title}</h4>
              <span class="diplomacy-doc-meta">${[doc.year, doc.type].filter(Boolean).join(' · ')}</span>
            </div>
            <p>${doc.description || ''}</p>
          `;
          docsEl.appendChild(docCard);
        });
      }
    }

    // ── Embassies section ──
    if (embassyOut > 0 || embassyIn > 0) {
      const embCard = this._createCard();
      let embHTML = '<div class="dip-section-title">🏛️ Дипломатические миссии</div>';

      if (embassyOut > 0) {
        embHTML += `<div class="dip-subtitle">Посольства ${displayName} за рубежом (${embassyOut})</div>`;
        embHTML += '<div class="dip-tag-list">';
        (embassies.has_embassy_in || []).slice(0, 30).forEach(iso => {
          embHTML += `<span class="dip-tag">${this._resolveName(iso)}</span>`;
        });
        if (embassyOut > 30) embHTML += `<span class="dip-tag dip-more">+${embassyOut - 30}</span>`;
        embHTML += '</div>';
      }

      if (embassyIn > 0) {
        embHTML += `<div class="dip-subtitle">Иностранные посольства в ${displayName} (${embassyIn})</div>`;
        embHTML += '<div class="dip-tag-list">';
        (embassies.embassies_from || []).slice(0, 30).forEach(iso => {
          embHTML += `<span class="dip-tag">${this._resolveName(iso)}</span>`;
        });
        if (embassyIn > 30) embHTML += `<span class="dip-tag dip-more">+${embassyIn - 30}</span>`;
        embHTML += '</div>';
      }

      embCard.innerHTML = embHTML;
      docsEl.appendChild(embCard);
    }

    // ── Top 5 Partners (green) ──
    if (topPartners.length > 0) {
      const parCard = this._createCard('dip-positive');
      let parHTML = '<div class="dip-section-title dip-positive-title">🟢 Топ-5 ключевых партнёров</div>';
      parHTML += '<div class="dip-rank-list">';
      topPartners.forEach((iso, i) => {
        const t = tone[iso];
        const toneVal = t?.tone ?? null;
        const count = t?.count ?? 0;
        const trend = t?.trend ?? 'stable';
        const trendIcon = trend === 'up' ? '📈' : trend === 'down' ? '📉' : '➡️';
        const toneStr = toneVal !== null ? `${toneVal > 0 ? '+' : ''}${toneVal.toFixed(1)}` : '—';
        const toneColor = toneVal > 2 ? '#4caf50' : toneVal < -2 ? '#f44336' : '#ffc107';
        parHTML += `
          <div class="dip-rank-item">
            <span class="dip-rank-num">${i + 1}</span>
            <span class="dip-rank-name">${this._resolveName(iso)}</span>
            <span class="dip-rank-tone" style="color:${toneColor}">${toneStr}</span>
            <span class="dip-rank-count">${count} ст.</span>
            <span>${trendIcon}</span>
          </div>`;
      });
      parHTML += '</div>';
      parCard.innerHTML = parHTML;
      docsEl.appendChild(parCard);
    }

    // ── Top 5 Adversaries (red) ──
    if (topAdversaries.length > 0) {
      const advCard = this._createCard('dip-negative');
      let advHTML = '<div class="dip-section-title dip-negative-title">🔴 Топ-5 напряжённых отношений</div>';
      advHTML += '<div class="dip-rank-list">';
      topAdversaries.forEach((iso, i) => {
        const t = tone[iso];
        const toneVal = t?.tone ?? null;
        const count = t?.count ?? 0;
        const trend = t?.trend ?? 'stable';
        const trendIcon = trend === 'up' ? '📈' : trend === 'down' ? '📉' : '➡️';
        const toneStr = toneVal !== null ? `${toneVal > 0 ? '+' : ''}${toneVal.toFixed(1)}` : '—';
        const toneColor = toneVal > 2 ? '#4caf50' : toneVal < -2 ? '#f44336' : '#ffc107';
        advHTML += `
          <div class="dip-rank-item">
            <span class="dip-rank-num">${i + 1}</span>
            <span class="dip-rank-name">${this._resolveName(iso)}</span>
            <span class="dip-rank-tone" style="color:${toneColor}">${toneStr}</span>
            <span class="dip-rank-count">${count} ст.</span>
            <span>${trendIcon}</span>
          </div>`;
      });
      advHTML += '</div>';
      advCard.innerHTML = advHTML;
      docsEl.appendChild(advCard);
    }

    // ── Tone articles feed (latest 5 across all partners) ──
    const allArticles = [];
    Object.entries(tone).forEach(([iso, data]) => {
      (data.articles || []).forEach(a => {
        allArticles.push({ ...a, partnerIso3: iso });
      });
    });
    allArticles.sort((a, b) => (b.date || '').localeCompare(a.date || ''));

    if (allArticles.length > 0) {
      const artCard = this._createCard();
      let artHTML = '<div class="dip-section-title">📰 Свежие дипломатические заголовки</div>';
      allArticles.slice(0, 8).forEach(a => {
        const toneColor = (a.tone || 0) > 0 ? '#4caf50' : (a.tone || 0) < 0 ? '#f44336' : '#888';
        artHTML += `
          <div class="dip-article">
            <a href="${a.url || '#'}" target="_blank" rel="noopener" class="dip-article-title">${a.title || 'Без заголовка'}</a>
            <div class="dip-article-meta">
              <span style="color:${toneColor}">Тон: ${(a.tone || 0).toFixed(1)}</span>
              <span>· ${this._resolveName(a.partnerIso3)}</span>
              ${a.date ? `<span>· ${a.date.slice(0, 10)}</span>` : ''}
            </div>
          </div>`;
      });
      artCard.innerHTML = artHTML;
      docsEl.appendChild(artCard);
    }

    // ── Draw tone arcs on globe ──
    this._drawToneArcs(iso3, tone);
  }

  // ─────────────────────────────────────────────────────
  // Draw diplomacy arcs on the globe (color-coded by tone)
  // ─────────────────────────────────────────────────────
  _drawToneArcs(sourceIso3, tone) {
    const capsData = this.capitalsManager?.capitalsData;
    if (!capsData) return;

    const sourceCap = capsData[sourceIso3];
    if (!sourceCap) return;

    Object.entries(tone).forEach(([targetIso3, data]) => {
      const targetCap = capsData[targetIso3];
      if (!targetCap) return;

      const toneVal = data.tone || 0;
      const count = data.count || 0;
      if (count === 0) return; // skip partners with no data

      // Color: green for positive, red for negative, yellow for neutral
      let color;
      if (toneVal > 3) color = Cesium.Color.fromCssColorString('#4caf50').withAlpha(0.7);
      else if (toneVal < -3) color = Cesium.Color.fromCssColorString('#f44336').withAlpha(0.7);
      else color = Cesium.Color.fromCssColorString('#ffc107').withAlpha(0.5);

      // Great circle arc
      const path = this._computeGreatCirclePath(
        sourceCap.lat, sourceCap.lon,
        targetCap.lat, targetCap.lon,
        80
      );

      const ARC_HEIGHT = 600000;
      const positions = path.map((p, i) => {
        const t = i / (path.length - 1);
        const h = ARC_HEIGHT * 4 * t * (1 - t);
        return Cesium.Cartesian3.fromDegrees(p.lon, p.lat, h);
      });

      this.diplomacyEntities.push(this.viewer.entities.add({
        polyline: {
          positions,
          width: 2,
          material: color,
          clampToGround: false,
        },
      }));

      // Tone label at midpoint
      const midIdx = Math.floor(path.length / 2);
      const mid = path[midIdx];
      const midH = ARC_HEIGHT * 1.0 + 80000;
      const toneStr = `${toneVal > 0 ? '+' : ''}${toneVal.toFixed(1)}`;

      this.diplomacyEntities.push(this.viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(mid.lon, mid.lat, midH),
        label: {
          text: `${this._resolveName(targetIso3)} ${toneStr}`,
          font: 'bold 11px "Segoe UI", sans-serif',
          fillColor: color,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 30000000),
        },
      }));
    });
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
        lon: Math.atan2(y, x) * toDeg,
      });
    }
    return path;
  }

  // ─────────────────────────────────────────────────────
  // Helper: resolve ISO3 to display name
  // ─────────────────────────────────────────────────────
  _resolveName(iso3) {
    if (!iso3) return '—';
    const c = this.dataStore.get(iso3);
    if (c) return c.name_ru || c.name || iso3;
    // Fallback: try DiplomacyManager's own static name map
    const names = DiplomacyManager.COUNTRY_NAMES;
    return (names && names[iso3]) || iso3;
  }

  _createCard(extraClass) {
    const card = document.createElement('div');
    card.className = 'diplomacy-doc-card' + (extraClass ? ' ' + extraClass : '');
    return card;
  }

  _showNoData(iso3_1, iso3_2) {
    const name1 = this._resolveName(iso3_1);
    const name2 = this._resolveName(iso3_2);
    document.getElementById('diplomacyTitle').textContent = `${name1} — ${name2}`;
    document.getElementById('diplomacySummary').textContent =
      'Данные о дипломатических отношениях пока не загружены для этой пары стран.';
    document.getElementById('diplomacyDocs').innerHTML = '';
    document.getElementById('diplomacyPanel').classList.add('visible');
  }

  clear() {
    this.activeIso3 = null;
    // Remove globe entities
    if (this.diplomacyEntities) {
      this.diplomacyEntities.forEach(entity => {
        try { this.viewer.entities.remove(entity); } catch {}
      });
      this.diplomacyEntities = [];
    }
    const panel = document.getElementById('diplomacyPanel');
    if (panel) panel.classList.remove('visible');
  }
}

// Static country name lookup (fallback when DataStore doesn't have the name)
DiplomacyManager.COUNTRY_NAMES = {
  AFG: 'Афганистан', ALB: 'Албания', DZA: 'Алжир', AGO: 'Ангола',
  ARG: 'Аргентина', ARM: 'Армения', AUS: 'Австралия', AUT: 'Австрия',
  AZE: 'Азербайджан', BHS: 'Багамы', BHR: 'Бахрейн', BGD: 'Бангладеш',
  BLR: 'Беларусь', BEL: 'Бельгия', BLZ: 'Белиз', BEN: 'Бенин',
  BTN: 'Бутан', BOL: 'Боливия', BIH: 'Босния и Герцеговина',
  BWA: 'Ботсвана', BRA: 'Бразилия', BRN: 'Бруней', BGR: 'Болгария',
  BFA: 'Буркина-Фасо', BDI: 'Бурунди', KHM: 'Камбоджа', CMR: 'Камерун',
  CAN: 'Канада', TCD: 'Чад', CHL: 'Чили', CHN: 'Китай',
  COL: 'Колумбия', COG: 'Конго', COD: 'ДР Конго', CRI: 'Коста-Рика',
  CIV: "Кот-д'Ивуар", HRV: 'Хорватия', CUB: 'Куба', CYP: 'Кипр',
  CZE: 'Чехия', DNK: 'Дания', DJI: 'Джибути', DOM: 'Доминикана',
  ECU: 'Эквадор', EGY: 'Египет', SLV: 'Сальвадор', GNQ: 'Экваториальная Гвинея',
  ERI: 'Эритрея', EST: 'Эстония', ETH: 'Эфиопия', FIN: 'Финляндия',
  FRA: 'Франция', GAB: 'Габон', GMB: 'Гамбия', GEO: 'Грузия',
  DEU: 'Германия', GHA: 'Гана', GRC: 'Греция', GTM: 'Гватемала',
  GIN: 'Гвинея', GUY: 'Гайана', HTI: 'Гаити', HND: 'Гондурас',
  HUN: 'Венгрия', ISL: 'Исландия', IND: 'Индия', IDN: 'Индонезия',
  IRN: 'Иран', IRQ: 'Ирак', IRL: 'Ирландия', ISR: 'Израиль',
  ITA: 'Италия', JAM: 'Ямайка', JPN: 'Япония', JOR: 'Иордания',
  KAZ: 'Казахстан', KEN: 'Кения', KOR: 'Южная Корея', PRK: 'Северная Корея',
  KWT: 'Кувейт', KGZ: 'Кыргызстан', LAO: 'Лаос', LVA: 'Латвия',
  LBN: 'Ливан', LBR: 'Либерия', LBY: 'Ливия', LTU: 'Литва',
  LUX: 'Люксембург', MDG: 'Мадагаскар', MWI: 'Малави', MYS: 'Малайзия',
  MDV: 'Мальдивы', MLI: 'Мали', MLT: 'Мальта', MRT: 'Мавритания',
  MUS: 'Маврикий', MEX: 'Мексика', MDA: 'Молдова', MNG: 'Монголия',
  MNE: 'Черногория', MAR: 'Марокко', MOZ: 'Мозамбик', MMR: 'Мьянма',
  NAM: 'Намибия', NPL: 'Непал', NLD: 'Нидерланды', NZL: 'Новая Зеландия',
  NIC: 'Никарагуа', NER: 'Нигер', NGA: 'Нигерия', NOR: 'Норвегия',
  OMN: 'Оман', PAK: 'Пакистан', PAN: 'Панама', PNG: 'Папуа-Новая Гвинея',
  PRY: 'Парагвай', PER: 'Перу', PHL: 'Филиппины', POL: 'Польша',
  PRT: 'Португалия', QAT: 'Катар', ROU: 'Румыния', RUS: 'Россия',
  RWA: 'Руанда', SAU: 'Саудовская Аравия', SEN: 'Сенегал', SRB: 'Сербия',
  SLE: 'Сьерра-Леоне', SGP: 'Сингапур', SVK: 'Словакия', SVN: 'Словения',
  SOM: 'Сомали', ZAF: 'ЮАР', SSD: 'Южный Судан', ESP: 'Испания',
  LKA: 'Шри-Ланка', SDN: 'Судан', SWE: 'Швеция', CHE: 'Швейцария',
  SYR: 'Сирия', TWN: 'Тайвань', TJK: 'Таджикистан', TZA: 'Танзания',
  THA: 'Таиланд', TLS: 'Восточный Тимор', TGO: 'Того', TTO: 'Тринидад и Тобаго',
  TUN: 'Тунис', TUR: 'Турция', TKM: 'Туркменистан', UGA: 'Уганда',
  UKR: 'Украина', ARE: 'ОАЭ', GBR: 'Великобритания', USA: 'США',
  URY: 'Уругвай', UZB: 'Узбекистан', VEN: 'Венесуэла', VNM: 'Вьетнам',
  YEM: 'Йемен', ZMB: 'Замбия', ZWE: 'Зимбабве',
};
