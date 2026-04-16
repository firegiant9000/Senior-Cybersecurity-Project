const TZ_FORMATTER = new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
});

const TIME_ONLY_FORMATTER = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
});

/** Format an ISO UTC string as a full date+time in the user's local timezone, e.g. "Apr 15, 2026, 10:30:00 AM EDT" */
export function formatDateWithTz(isoString: string | null | undefined): string {
    if (!isoString) return '—';
    return TZ_FORMATTER.format(new Date(isoString));
}

/** Format a Date object as time-only in the user's local timezone, e.g. "10:30:00 AM EDT" */
export function formatTimeWithTz(date: Date | null | undefined): string {
    if (!date) return '—';
    return TIME_ONLY_FORMATTER.format(date);
}
