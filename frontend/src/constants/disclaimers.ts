import type { DisclaimerBlock } from '../types/disclaimer';

/**
 * Static disclaimer block for the SMB Risk Advisor tab.
 * This view aggregates multiple API calls and public data,
 * so the disclaimer is client-side rather than API-driven.
 */
export const SMB_ADVISOR_DISCLAIMER: DisclaimerBlock = {
  primary_text:
    'Data sourced from the FBI Internet Crime Complaint Center (IC3) and the National ' +
    'Vulnerability Database (NVD). Figures represent aggregated complaint data and may ' +
    'not reflect all incidents \u2014 the majority of cybercrimes go unreported.',
  confidence_text:
    'This tool provides educational guidance based on public threat intelligence data.',
  data_source_attribution: 'Data sources: FBI IC3, NIST NVD, CISA KEV',
  transparency_note:
    'Generated from available company-provided information and public threat intelligence data.',
};
