import InfoTip, { getAcronymDefinition } from './InfoTip';

export default function VictimImpactBadge() {
  return (
    <span className="victim-impact-badge">
      IC3<InfoTip text={getAcronymDefinition('IC3')!} label="IC3" /> Victim Financial Impact
    </span>
  );
}
