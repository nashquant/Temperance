const MONTHS: Record<string, string> = {
  jan: '01',
  feb: '02',
  mar: '03',
  apr: '04',
  may: '05',
  jun: '06',
  jul: '07',
  aug: '08',
  sep: '09',
  oct: '10',
  nov: '11',
  dec: '12',
};

function buildIsoDate(year: number, month: number, day: number): string | null {
  const candidate = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  const parsed = new Date(`${candidate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() + 1 !== month || parsed.getUTCDate() !== day) {
    return null;
  }
  return candidate;
}

export function normalizeCompactDateInput(rawValue: string): string | null {
  const value = rawValue.trim();
  if (!value) {
    return null;
  }

  const isoMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return buildIsoDate(Number(isoMatch[1]), Number(isoMatch[2]), Number(isoMatch[3]));
  }

  const slashMatch = value.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashMatch) {
    return buildIsoDate(Number(slashMatch[3]), Number(slashMatch[2]), Number(slashMatch[1]));
  }

  const compactMatch = value.match(/^(\d{1,2})([A-Za-z]{3})(\d{2})$/);
  if (compactMatch) {
    const month = MONTHS[compactMatch[2].toLowerCase()];
    if (!month) {
      return null;
    }
    return buildIsoDate(2000 + Number(compactMatch[3]), Number(month), Number(compactMatch[1]));
  }

  return null;
}
