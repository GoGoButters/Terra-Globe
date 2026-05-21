// Конфигурация легенд для каждого слоя
const legendConfig = {
    income: {
      title: 'Уровень дохода',
      items: [
        { color: '#1a9850', label: 'Высокий' },
        { color: '#91cf60', label: 'Выше среднего' },
        { color: '#fee08b', label: 'Ниже среднего' },
        { color: '#d73027', label: 'Низкий' },
        { color: '#888888', label: 'Нет данных' }
      ]
    },
    hdi: {
      title: 'Индекс человеческого развития',
      gradient: true,
      stops: [
        { value: 0.5, color: '#d73027', label: '0.5' },
        { value: 1.0, color: '#1a9850', label: '1.0' }
      ]
    },
    freedom: {
      title: 'Индекс свободы (Freedom House)',
      gradient: true,
      stops: [
        { value: 0, color: '#d73027', label: '0' },
        { value: 100, color: '#1a9850', label: '100' }
      ]
    }
  };
  
  function updateLegend(layer) {
    const config = legendConfig[layer];
    if (!config) return;
  
    document.querySelector('#legend h4').textContent = '📊 ' + config.title;
    const container = document.getElementById('legendContent');
    
    if (config.items) {
      // Дискретная легенда
      container.innerHTML = config.items.map(item => `
        <div class="legend-item">
          <div class="legend-color" style="background: ${item.color}"></div>
          <span class="legend-label">${item.label}</span>
        </div>
      `).join('');
    } else if (config.stops) {
      // Градиентная легенда
      const gradientColors = config.stops.map(s => s.color).join(', ');
      container.innerHTML = `
        <div class="legend-item">
          <div class="legend-color" style="background: linear-gradient(to right, ${gradientColors}); width: 100%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 11px;">
          <span>${config.stops[0].label}</span>
          <span>${config.stops[1].label}</span>
        </div>
      `;
    }
  }
  
  // Обновляем легенду при загрузке и переключении слоя
  document.addEventListener('DOMContentLoaded', () => {
    updateLegend('income');
  });
  
  // Модифицируем switchLayer в layers.js, чтобы вызывать обновление легенды
  const originalSwitchLayer = switchLayer;
  switchLayer = function(layer) {
    originalSwitchLayer(layer);
    updateLegend(layer);
  };