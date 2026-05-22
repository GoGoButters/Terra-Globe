/**
 * AuthManager — handles authentication UI: auth gate, login/register forms,
 * Google OAuth, and post-login user menu in the bottom bar.
 */

class AuthManager {
  constructor() {
    this.user = null;
    this.onAuthChange = null; // callback when auth state changes
    this._dropdownOpen = false;
  }

  async init() {
    // Handle OAuth callback from Google redirect
    this._handleOAuthCallback();

    // Load existing tokens and validate
    if (API.loadTokens()) {
      try {
        this.user = await API.getMe();
      } catch (e) {
        API.clearTokens();
        this.user = null;
      }
    }

    // Initialize UI based on auth state
    this._initAuthGate();
    this._initBottomBarAuth();
    this._updateAllUI();

    // If already authenticated, dismiss gate immediately
    if (this.user) {
      this._dismissGate();
    } else {
      this._createParticles();
    }
  }

  // ── Auth Gate ─────────────────────────────────────────────

  _initAuthGate() {
    const gate = document.getElementById('authGate');
    if (!gate) return;

    // Tab switching
    gate.querySelectorAll('.auth-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        gate.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.getElementById('authLoginForm').classList.toggle('hidden', target !== 'login');
        document.getElementById('authRegisterForm').classList.toggle('hidden', target !== 'register');
        // Clear errors
        this._hideError('authLoginError');
        this._hideError('authRegisterError');
      });
    });

    // Login form
    document.getElementById('authLoginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('authLoginEmail').value;
      const password = document.getElementById('authLoginPassword').value;
      await this._submitLogin(email, password);
    });

    // Register form
    document.getElementById('authRegisterForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('authRegisterEmail').value;
      const username = document.getElementById('authRegisterUsername').value;
      const password = document.getElementById('authRegisterPassword').value;
      await this._submitRegister(email, username, password);
    });

    // Google button
    document.getElementById('authGoogleBtn').addEventListener('click', () => {
      this._googleLogin();
    });
  }

  async _submitLogin(email, password) {
    const btn = document.getElementById('authLoginSubmit');
    const errorEl = document.getElementById('authLoginError');

    btn.classList.add('loading');
    btn.disabled = true;
    this._hideError('authLoginError');

    try {
      await API.login(email, password);
      this.user = await API.getMe();
      this._updateAllUI();
      this._dismissGate();
    } catch (err) {
      this._showError('authLoginError', err.message || 'Не удалось войти. Проверьте данные.');
    } finally {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  }

  async _submitRegister(email, username, password) {
    const btn = document.getElementById('authRegisterSubmit');
    const errorEl = document.getElementById('authRegisterError');

    btn.classList.add('loading');
    btn.disabled = true;
    this._hideError('authRegisterError');

    try {
      await API.register(email, username, password);
      this.user = await API.getMe();
      this._updateAllUI();
      this._dismissGate();
    } catch (err) {
      this._showError('authRegisterError', err.message || 'Не удалось зарегистрироваться. Попробуйте другое имя.');
    } finally {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  }

  _dismissGate() {
    const gate = document.getElementById('authGate');
    if (gate) {
      gate.classList.add('dismissed');
      // Remove from DOM after transition
      setTimeout(() => {
        if (gate.classList.contains('dismissed')) {
          gate.style.display = 'none';
        }
      }, 700);
    }
  }

  _showGate() {
    const gate = document.getElementById('authGate');
    if (gate) {
      gate.style.display = 'flex';
      // Force reflow
      gate.offsetHeight;
      gate.classList.remove('dismissed');
    }
  }

  _createParticles() {
    const container = document.getElementById('authParticles');
    if (!container) return;

    for (let i = 0; i < 30; i++) {
      const particle = document.createElement('div');
      particle.className = 'auth-particle';
      particle.style.left = Math.random() * 100 + '%';
      particle.style.animationDuration = (8 + Math.random() * 12) + 's';
      particle.style.animationDelay = Math.random() * 10 + 's';
      particle.style.width = (1 + Math.random() * 2) + 'px';
      particle.style.height = particle.style.width;
      particle.style.opacity = 0.2 + Math.random() * 0.4;
      container.appendChild(particle);
    }
  }

  // ── Bottom Bar Auth (post-login) ────────────────────────

  _initBottomBarAuth() {
    // Create auth panel in bottom bar
    if (document.getElementById('authPanel')) return;

    const panel = document.createElement('div');
    panel.id = 'authPanel';
    panel.className = 'auth-container';
    panel.innerHTML = `
      <div id="authLoggedIn" style="display:none;">
        <div class="auth-user-menu">
          <button class="auth-user-trigger" id="authUserTrigger">
            <img id="authAvatar" src="" alt="" class="avatar-sm" style="display:none;">
            <span id="authUsername"></span>
            <span class="chevron">▼</span>
          </button>
          <div class="auth-dropdown" id="authDropdown">
            <div class="auth-dropdown-header">
              <div class="name" id="dropdownName"></div>
              <div class="email" id="dropdownEmail"></div>
            </div>
            <button class="auth-dropdown-item danger" id="authLogoutBtn">
              <span>⏻</span> Выйти
            </button>
          </div>
        </div>
      </div>
      <div id="authLoggedOut" style="display:none;">
        <button id="authLoginBtn" class="auth-btn">Войти</button>
      </div>
    `;

    const bottomPanel = document.getElementById('bottomPanel');
    if (bottomPanel) {
      bottomPanel.appendChild(panel);
    } else {
      document.body.appendChild(panel);
    }

    // Event listeners
    document.getElementById('authLoginBtn')?.addEventListener('click', () => {
      this._showGate();
    });

    document.getElementById('authLogoutBtn')?.addEventListener('click', () => {
      this.logout();
    });

    // Dropdown toggle
    const trigger = document.getElementById('authUserTrigger');
    const dropdown = document.getElementById('authDropdown');

    trigger?.addEventListener('click', (e) => {
      e.stopPropagation();
      this._dropdownOpen = !this._dropdownOpen;
      trigger.classList.toggle('open', this._dropdownOpen);
      dropdown.classList.toggle('visible', this._dropdownOpen);
    });

    // Close dropdown on outside click
    document.addEventListener('click', () => {
      if (this._dropdownOpen) {
        this._dropdownOpen = false;
        trigger?.classList.remove('open');
        dropdown?.classList.remove('visible');
      }
    });
  }

  // ── UI Updates ──────────────────────────────────────────

  _updateAllUI() {
    this._updateGateUI();
    this._updateBottomBarUI();

    if (this.onAuthChange) {
      this.onAuthChange(!!this.user, this.user);
    }
  }

  _updateGateUI() {
    // Gate is dismissed when authenticated, shown when not
    // This is handled by _dismissGate() and _showGate()
  }

  _updateBottomBarUI() {
    const loggedIn = document.getElementById('authLoggedIn');
    const loggedOut = document.getElementById('authLoggedOut');

    if (!loggedIn || !loggedOut) return;

    if (this.user) {
      loggedIn.style.display = 'block';
      loggedOut.style.display = 'none';

      document.getElementById('authUsername').textContent = this.user.username;
      document.getElementById('dropdownName').textContent = this.user.username;
      document.getElementById('dropdownEmail').textContent = this.user.email || '';

      const avatar = document.getElementById('authAvatar');
      if (this.user.avatar_url) {
        avatar.src = this.user.avatar_url;
        avatar.style.display = 'block';
      } else {
        avatar.style.display = 'none';
      }
    } else {
      loggedIn.style.display = 'none';
      loggedOut.style.display = 'block';
    }
  }

  // ── Google OAuth ────────────────────────────────────────

  _googleLogin() {
    const width = 500;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const popup = window.open(
      `${API.baseUrl}/auth/google/login`,
      'google-auth',
      `width=${width},height=${height},left=${left},top=${top}`
    );

    if (!popup) {
      // Popup blocked — redirect in same window
      window.location.href = `${API.baseUrl}/auth/google/login`;
      return;
    }

    // Listen for callback via postMessage
    const handleMessage = (event) => {
      if (event.data && event.data.type === 'oauth-callback') {
        window.removeEventListener('message', handleMessage);
        if (event.data.access_token && event.data.refresh_token) {
          API.setTokens(event.data.access_token, event.data.refresh_token);
          API.getMe().then(user => {
            this.user = user;
            this._updateAllUI();
            this._dismissGate();
          }).catch(() => {});
        }
        popup.close();
      }
    };
    window.addEventListener('message', handleMessage);

    // Fallback: poll for closed popup
    const checkClosed = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkClosed);
        window.removeEventListener('message', handleMessage);
        if (API.loadTokens()) {
          API.getMe().then(user => {
            this.user = user;
            this._updateAllUI();
            this._dismissGate();
          }).catch(() => {});
        }
      }
    }, 500);
  }

  _handleOAuthCallback() {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');

    if (accessToken && refreshToken) {
      API.setTokens(accessToken, refreshToken);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  // ── Logout ──────────────────────────────────────────────

  async logout() {
    await API.logout();
    this.user = null;
    this._updateAllUI();
    this._showGate();
  }

  // ── Helpers ─────────────────────────────────────────────

  _showError(id, message) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = message;
      el.classList.add('visible');
    }
  }

  _hideError(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove('visible');
    }
  }

  isAuthenticated() {
    return !!this.user;
  }
}
