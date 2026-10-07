type CurrencyValue = number | string | null | undefined;

export const currency = (value: CurrencyValue, currencyCode = "USD"): string =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currencyCode,
  }).format(Number(value || 0));

export const pretty = (value: string): string =>
  value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
