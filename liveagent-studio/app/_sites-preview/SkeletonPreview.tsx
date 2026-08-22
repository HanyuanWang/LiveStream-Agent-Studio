"use client";

import Skeleton, { SkeletonTheme } from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import "./preview.css";

const sidebarWidths = [74, 58, 82, 66, 71, 54] as const;
const articleWidths = [100, 97, 94, 98, 86] as const;

export function SkeletonPreview() {
  return (
    <SkeletonTheme
      baseColor="#eceae7"
      highlightColor="#f9f8f6"
      duration={2.8}
      borderRadius="0.5rem"
      inline
    >
      <main className="sites-skeleton-preview">
        <header className="sites-skeleton-header" aria-hidden="true">
          <div className="sites-skeleton-brand">
            <Skeleton circle width={34} height={34} />
            <Skeleton width={112} height={14} />
          </div>

          <div className="sites-skeleton-search">
            <Skeleton
              width="100%"
              height={36}
              borderRadius={10}
              containerClassName="sites-skeleton-search-placeholder"
            />
          </div>

          <div className="sites-skeleton-actions">
            <Skeleton circle width={34} height={34} />
            <Skeleton width={94} height={34} borderRadius={8} />
          </div>
        </header>

        <div className="sites-skeleton-shell" aria-hidden="true">
          <aside className="sites-skeleton-sidebar">
            <Skeleton
              width={66}
              height={10}
              containerClassName="sites-skeleton-sidebar-heading"
            />
            <div className="sites-skeleton-sidebar-list">
              {sidebarWidths.map((width, index) => (
                <div
                  className="sites-skeleton-sidebar-row"
                  key={`${width}-${index}`}
                >
                  <Skeleton width={18} height={18} borderRadius={5} />
                  <Skeleton width={`${width}%`} height={10} />
                </div>
              ))}
            </div>
            <Skeleton
              width={92}
              height={10}
              containerClassName="sites-skeleton-sidebar-heading sites-skeleton-sidebar-heading-secondary"
            />
            <div className="sites-skeleton-sidebar-list">
              {sidebarWidths.slice(0, 3).map((width, index) => (
                <div
                  className="sites-skeleton-sidebar-row"
                  key={`secondary-${width}-${index}`}
                >
                  <Skeleton width={18} height={18} borderRadius={5} />
                  <Skeleton width={`${width - 12}%`} height={10} />
                </div>
              ))}
            </div>
          </aside>

          <article className="sites-skeleton-article">
            <div className="sites-skeleton-article-heading">
              <Skeleton width={118} height={10} />
              <Skeleton width="82%" height={28} />
              <Skeleton width="58%" height={28} />
            </div>

            <Skeleton
              containerClassName="sites-skeleton-article-media"
              height="100%"
              borderRadius={14}
            />

            <div className="sites-skeleton-article-meta">
              <Skeleton circle width={32} height={32} />
              <div className="sites-skeleton-article-author">
                <Skeleton width={116} height={10} />
                <Skeleton width={82} height={8} />
              </div>
              <Skeleton
                width={76}
                height={10}
                containerClassName="sites-skeleton-article-date"
              />
            </div>

            <div className="sites-skeleton-article-copy">
              {articleWidths.map((width, index) => (
                <Skeleton
                  key={`${width}-${index}`}
                  width={`${width}%`}
                  height={10}
                />
              ))}
            </div>
          </article>

          <aside className="sites-skeleton-rail">
            <div className="sites-skeleton-rail-card">
              <Skeleton circle width={48} height={48} />
              <Skeleton width="62%" height={13} />
              <Skeleton width="92%" height={9} />
              <Skeleton width="74%" height={9} />
              <Skeleton width={104} height={34} borderRadius={8} />
            </div>
            <div className="sites-skeleton-rail-card sites-skeleton-rail-card-compact">
              <Skeleton width="54%" height={13} />
              <Skeleton height={72} borderRadius={10} />
              <Skeleton width="78%" height={48} borderRadius={10} />
            </div>
          </aside>
        </div>

        <section
          className="sites-skeleton-status"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <span className="sites-skeleton-status-kicker">
            Building your site
          </span>
          <h1>Your site is taking shape</h1>
          <p>Your first version will appear here automatically when it’s ready.</p>
        </section>
      </main>
    </SkeletonTheme>
  );
}
