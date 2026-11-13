import { Link } from "react-router-dom";

interface NotFoundPageProps {
  /** Rendered inside the app shell's <main>: use a section so there is only one main landmark. */
  embedded?: boolean;
}

export default function NotFoundPage({ embedded = false }: NotFoundPageProps) {
  const content = (
    <>
      <h1>Page not found</h1>
      <p>The page you are looking for does not exist or has moved.</p>
      <Link to="/">Go to the Overview</Link>
    </>
  );
  return embedded ? (
    <section data-testid="not-found-page">{content}</section>
  ) : (
    <main data-testid="not-found-page">{content}</main>
  );
}
