import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main data-testid="not-found-page">
      <h1>Page not found</h1>
      <p>The page you are looking for does not exist or has moved.</p>
      <Link to="/">Go to the Overview</Link>
    </main>
  );
}
