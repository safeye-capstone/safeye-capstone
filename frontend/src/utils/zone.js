const normalize = (s) => (s ?? "").replace(/\s/g, "");

export function parseZoneName(fileName) {
  const base = fileName.replace(/\.[^.]+$/, "");
  return base.split("_")[0].trim();
}

export function matchZone(zones, fileName) {
  const parsed = normalize(parseZoneName(fileName));
  if (!parsed) return null;
  return zones.find((z) => normalize(z.zoneName) === parsed) ?? null;
}
