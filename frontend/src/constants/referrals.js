// "הובא על ידי" (חבר מביא חבר). Must match REFERRER_MAX_LENGTH in
// backend/app/models/candidate.py (backend/tests/test_referrals.py).
export const REFERRER_MAX_LENGTH = 100;
export const REFERRER_LABEL = 'הובא על ידי';

/* Same cleanup as the backend: trim and collapse inner spaces */
export const cleanReferrer = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();
