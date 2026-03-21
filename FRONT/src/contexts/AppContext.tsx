import React, { createContext, useContext, useEffect, useState } from 'react';
import { translations, type Lang } from '../i18n/translations';
import { safeStorage } from '../utils/safeStorage';

type Theme = 'light' | 'dark';

interface AppCtx {
  lang:     Lang;
  theme:    Theme;
  t:        (key: string) => string;
  setLang:  (l: Lang)  => void;
  setTheme: (t: Theme) => void;
}

const AppContext = createContext<AppCtx>({
  lang: 'en', theme: 'light',
  t: k => k, setLang: () => {}, setTheme: () => {},
});

const LS_LANG  = 'iq_lang';
const LS_THEME = 'iq_theme';

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang,  setLangState]  = useState<Lang>( () => (safeStorage.getItem(LS_LANG)  as Lang)  || 'en');
  const [theme, setThemeState] = useState<Theme>(() => (safeStorage.getItem(LS_THEME) as Theme) || 'light');

  /* Sync <html dir> and <html lang> */
  useEffect(() => {
    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('dir',  lang === 'he' ? 'rtl' : 'ltr');
  }, [lang]);

  /* Sync <html class="dark"> */
  useEffect(() => {
    if (theme === 'dark') document.documentElement.classList.add('dark');
    else                  document.documentElement.classList.remove('dark');
  }, [theme]);

  const setLang  = (l: Lang)  => { setLangState(l);  safeStorage.setItem(LS_LANG,  l); };
  const setTheme = (t: Theme) => { setThemeState(t); safeStorage.setItem(LS_THEME, t); };

  const t = (key: string): string =>
    translations[lang]?.[key] ?? translations['en']?.[key] ?? key;

  return (
    <AppContext.Provider value={{ lang, theme, t, setLang, setTheme }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => useContext(AppContext);
