(() => {
  const toggle = document.querySelector('[data-theme-toggle]');
  const setTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('securepay-theme', theme);
    if (toggle) {
      toggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
      toggle.setAttribute('title', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
    }
  };

  if (toggle) {
    setTheme(document.documentElement.dataset.theme || 'light');
    toggle.addEventListener('click', () => {
      setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    });
  }

  document.querySelector('[data-back-to-top]')?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });
})();
