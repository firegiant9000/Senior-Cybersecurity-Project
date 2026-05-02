import { useNavigate } from 'react-router-dom';
import { getGlossaryEntries } from '../components/shared/InfoTip';
import '../Dashboard.css';
import './GlossaryPage.css';

export default function GlossaryPage() {
  const navigate = useNavigate();
  const entries = getGlossaryEntries();

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Glossary</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate('/')}>
            Back to Dashboard
          </button>
        </div>
      </header>

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
    </div>
  );
}
