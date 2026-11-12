import { useEffect, useState } from 'react';
import {
  fetchGeographicHeatmap,
  fetchSectorAttackMatrix,
  fetchIndustryRisk,
  fetchAttackTypes,
  type GeographicThreat,
  type SectorAttackCombination,
  type IndustryRiskProfile,
  type AttackTypeStats,
} from '../api/dashboardSummary';

interface IncidentLandscapeData {
  geographicThreats: GeographicThreat[];
  sectorAttackMatrix: SectorAttackCombination[];
  industryRisk: IndustryRiskProfile[];
  attackTypes: AttackTypeStats[];
  loading: boolean;
  errors: string[];
}

const EMPTY: IncidentLandscapeData = {
  geographicThreats: [],
  sectorAttackMatrix: [],
  industryRisk: [],
  attackTypes: [],
  loading: true,
  errors: [],
};

export function useIncidentLandscape(): IncidentLandscapeData {
  const [state, setState] = useState<IncidentLandscapeData>(EMPTY);

  useEffect(() => {
    const ctrl = new AbortController();
    const { signal } = ctrl;

    Promise.allSettled([
      fetchGeographicHeatmap(signal),
      fetchSectorAttackMatrix(signal),
      fetchIndustryRisk(signal),
      fetchAttackTypes(signal),
    ]).then(([geo, matrix, risk, types]) => {
      if (signal.aborted) return;
      const errors: string[] = [];
      const items = <T,>(r: PromiseSettledResult<{ items: T[] }>, label: string): T[] => {
        if (r.status === 'fulfilled') return r.value.items;
        errors.push(`${label} could not be loaded.`);
        return [];
      };
      setState({
        geographicThreats: items(geo, 'Geographic threat data'),
        sectorAttackMatrix: items(matrix, 'Sector and attack type data'),
        industryRisk: items(risk, 'Sector impact data'),
        attackTypes: items(types, 'Attack type data'),
        loading: false,
        errors,
      });
    });

    return () => ctrl.abort();
  }, []);

  return state;
}
