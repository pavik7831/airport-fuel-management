export const currency = (n, c = "USD") =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: c }).format(
    Number(n || 0),
  );
export const pretty = (s) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (x) => x.toUpperCase());
