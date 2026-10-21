import type { PageDef } from "../pages/pages";

/** Honest placeholder for modules scheduled for later phases. No data, no controls. */
export function PageStub({ page }: { page: PageDef }) {
  return (
    <div className="page">
      <h1>{page.title}</h1>
      <p className="sub">{page.summary}</p>
      <div className="emptybox"><strong>Not available yet</strong><div className="muted">This module is planned for phase {page.phase}.</div></div>
    </div>);
}
