import { getGlossaryEntries } from '../components/shared/InfoTip';
import './GlossaryPage.css';

export default function GlossaryPage() {
  const entries = getGlossaryEntries();

  return (
    <>
      <h1>Glossary</h1>

      <div className="glossary-page">
        <div className="glossary-card">
          <p className="glossary-intro">
            Plain-language definitions for the cybersecurity terms used across this dashboard.
            Click any ⓘ icon in the app for the same definition inline.
          </p>
          <dl className="glossary-list">
            {entries.map(({ term, definition }) => (
              <div key={term} className="glossary-entry">
                <dt className="glossary-term">{term}</dt>
                <dd className="glossary-definition">{definition}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </>
  );
}
