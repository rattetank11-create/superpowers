import { ru, type MessageKey } from "./ru";

const dictionaries = { ru } as const;
export type Locale = keyof typeof dictionaries;

// Пока один язык. Для i18n: добавить словарь в dictionaries и брать locale из URL/cookie.
export const defaultLocale: Locale = "ru";

export function t(key: MessageKey, params?: Record<string, string | number>, locale: Locale = defaultLocale): string {
  const template: string = dictionaries[locale][key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}

export function hasKey(key: string): key is MessageKey {
  return key in dictionaries[defaultLocale];
}

export type { MessageKey };
