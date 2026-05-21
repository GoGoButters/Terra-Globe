/**
 * AuthManager — handles authentication UI: login modal, user display, Google OAuth.
 */

class AuthManager {
  constructor() {
    this.user = null;
    this.onAuthChange = null; // callback when auth state changes
  }

  async init() {
    // Load existing tokens
    if (API.loadTokens()) {
      try {
        this.user = await API.getMe();
        this._updateUI();
      } catch (e) {
        API.clearTokens();
        this.user = null;
      }
    }

    this._createAuthUI();
    this._updateUI();
  }

  _createAuthUI() {
    // Create auth panel if it doesn't exist
    if (document.getElementById('authPanel')) return;

    const panel = document.createElement('div');
    panel.id = 'authPanel';
    panel.innerHTML = `
      <div class="auth-container">
        <div id="authLoggedIn" style="display:none;">
          <div class="auth-user-info">
            <img id="authAvatar" src="" alt="" class="auth-avatar" style="display:none;">
            <span id="authUsername" class="auth-username"></span>
          </div>
          <button id="authLogoutBtn" class="auth-btn auth-btn-logout">Выйти</button>
        </div>
        <div id="authLoggedOut">
          <button id="authLoginBtn" class="auth-btn auth-btn-login">Войти</button>
          <button id="authGoogleBtn" class="auth-btn auth-btn-google">
            <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 7.07 5.48 3.56 13.28l7.91 6.16C13.18 12.09 18.16 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.6c-.52-1.56-.82-3.22-.82-4.94s.3-3.38.82-4.94l-7.91-6.16C.97 15.82 0 19.79 0 24s.97 8.18 2.62 11.44l7.91-6.84z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-5.84 0-10.82-3.91-12.53-9.2l-7.91 6.16C7.07 42.52 14.62 48 24 48z"/></svg>
            Google
          </button>
        </div>
      </div>
    `;

    // Insert into bottom panel
    const bottomPanel = document.getElementById('bottomPanel');
    if (bottomPanel) {
      bottomPanel.insertBefore(panel, bottomPanel.firstChild);
    } else {
      document.body.appendChild(panel);
    }

    // Event listeners with null guards
    const loginBtn = document.getElementById('authLoginBtn');
    if (loginBtn) loginBtn.addEventListener('click', () => this._showLoginModal());

    const googleBtn = document.getElementById('authGoogleBtn');
    if (googleBtn) googleBtn.addEventListener('click', () => this._googleLogin());

    const logoutBtn = document.getElementById('authLogoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', () => this.logout());
  }

  _updateUI() {
    const loggedIn = document.getElementById('authLoggedIn');
    const loggedOut = document.getElementById('authLoggedOut');

    if (!loggedIn || !loggedOut) return;

    if (this.user) {
      loggedIn.style.display = 'flex';
      loggedOut.style.display = 'none';
      document.getElementById('authUsername').textContent = this.user.username;

      const avatar = document.getElementById('authAvatar');
      if (this.user.avatar_url) {
        avatar.src = this.user.avatar_url;
        avatar.style.display = 'block';
      } else {
        avatar.style.display = 'none';
      }
    } else {
      loggedIn.style.display = 'none';
      loggedOut.style.display = 'flex';
    }

    if (this.onAuthChange) {
      this.onAuthChange(!!this.user, this.user);
    }
  }

  _showLoginModal() {
    // Remove existing modal
    const existing = document.getElementById('loginModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'loginModal';
    modal.className = 'login-modal-overlay';
    modal.innerHTML = `
      <div class="login-modal">
        <div class="login-modal-header">
          <h3>Вход в TerraGlobe</h3>
          <button class="login-modal-close">&times;</button>
        </div>
        <div class="login-modal-tabs">
          <button class="login-tab active" data-tab="login">Вход</button>
          <button class="login-tab" data-tab="register">Регистрация</button>
        </div>
        <form id="loginForm" class="login-form">
          <input type="email" id="loginEmail" placeholder="Email" required>
          <input type="password" id="loginPassword" placeholder="Пароль" required minlength="8">
          <button type="submit" class="login-submit-btn">Войти</button>
          <div id="loginError" class="login-error" style="display:none;"></div>
        </form>
        <form id="registerForm" class="login-form" style="display:none;">
          <input type="email" id="registerEmail" placeholder="Email" required>
          <input type="text" id="registerUsername" placeholder="Имя пользователя" required minlength="3" pattern="[a-zA-Z0-9_-]+">
          <input type="password" id="registerPassword" placeholder="Пароль" required minlength="8">
          <button type="submit" class="login-submit-btn">Зарегистрироваться</button>
          <div id="registerError" class="login-error" style="display:none;"></div>
        </form>
        <div class="login-divider">или</div>
        <button id="modalGoogleBtn" class="auth-btn auth-btn-google modal-google-btn">
          <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 7.07 5.48 3.56 13.28l7.91 6.16C13.18 12.09 18.16 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.6c-.52-1.56-.82-3.22-.82-4.94s.3-3.38.82-4.94l-7.91-6.16C.97 15.82 0 19.79 0 24s.97 8.18 2.62 11.44l7.91-6.84z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-5.84 0-10.82-3.91-12.53-9.2l-7.91 6.16C7.07 42.52 14.62 48 24 48z"/></svg>
          Войти через Google
        </button>
      </div>
    `;

    document.body.appendChild(modal);

    // Close handler
    modal.querySelector('.login-modal-close').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    // Tab switching
    modal.querySelectorAll('.login-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        modal.querySelectorAll('.login-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.getElementById('loginForm').style.display = target === 'login' ? 'block' : 'none';
        document.getElementById('registerForm').style.display = target === 'register' ? 'block' : 'none';
      });
    });

    // Login form
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('loginEmail').value;
      const password = document.getElementById('loginPassword').value;
      const errorEl = document.getElementById('loginError');

      try {
        await API.login(email, password);
        this.user = await API.getMe();
        this._updateUI();
        modal.remove();
      } catch (err) {
        errorEl.textContent = err.message || 'Не удалось войти. Проверьте данные.';
        errorEl.style.display = 'block';
      }
    });

    // Register form
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('registerEmail').value;
      const username = document.getElementById('registerUsername').value;
      const password = document.getElementById('registerPassword').value;
      const errorEl = document.getElementById('registerError');

      try {
        await API.register(email, username, password);
        this.user = await API.getMe();
        this._updateUI();
        modal.remove();
      } catch (err) {
        errorEl.textContent = err.message || 'Не удалось зарегистрироваться. Попробуйте другое имя.';
        errorEl.style.display = 'block';
      }
    });

    // Google login in modal
    document.getElementById('modalGoogleBtn').addEventListener('click', () => {
      modal.remove();
      this._googleLogin();
    });
  }

  _googleLogin() {
    // Open Google OAuth in popup
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
      // Popup blocked — redirect in same window instead
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
            this._updateUI();
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
        // Check if tokens were set
        if (API.loadTokens()) {
          API.getMe().then(user => {
            this.user = user;
            this._updateUI();
          }).catch(() => {});
        }
      }
    }, 500);
  }

  async logout() {
    await API.logout();
    this.user = null;
    this._updateUI();
  }
}

// Handle OAuth callback from Google redirect
function handleOAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const accessToken = params.get('access_token');
  const refreshToken = params.get('refresh_token');

  if (accessToken && refreshToken) {
    API.setTokens(accessToken, refreshToken);
    // Clean URL
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

// Run on load
handleOAuthCallback();
