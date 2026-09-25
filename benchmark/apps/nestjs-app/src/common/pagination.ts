export const PER_PAGE = 20;

export interface Paginated<T> {
  current_page: number;
  data: T[];
  first_page_url: string;
  from: number | null;
  last_page: number;
  last_page_url: string;
  links: Array<{ url: string | null; label: string; page: number | null; active: boolean }>;
  next_page_url: string | null;
  path: string;
  per_page: number;
  prev_page_url: string | null;
  to: number | null;
  total: number;
}

export function resolvePage(raw: unknown): number {
  const page = Number.parseInt(String(raw ?? '1'), 10);
  return Number.isNaN(page) || page < 1 ? 1 : page;
}

function pageUrl(path: string, page: number): string {
  return `${path}?page=${page}`;
}

// Mirrors Laravel LengthAwarePaginator::linkCollection() with onEachSide(2).
function buildLinks(
  path: string,
  page: number,
  lastPage: number,
): Paginated<unknown>['links'] {
  const pages: Array<number | 'dots'> = [];
  const onEachSide = 3;

  if (lastPage < onEachSide * 2 + 8) {
    for (let i = 1; i <= lastPage; i += 1) pages.push(i);
  } else if (page <= onEachSide + 2) {
    const lastInWindow = onEachSide * 2 + 2;
    for (let i = 1; i <= lastInWindow; i += 1) pages.push(i);
    pages.push('dots', lastPage);
  } else if (page >= lastPage - (onEachSide + 1)) {
    pages.push(1, 'dots');
    for (let i = lastPage - (onEachSide * 2 + 1); i <= lastPage; i += 1) pages.push(i);
  } else {
    pages.push(1, 'dots');
    for (let i = page - onEachSide; i <= page + onEachSide; i += 1) pages.push(i);
    pages.push('dots', lastPage);
  }

  const links: Paginated<unknown>['links'] = [
    {
      url: page > 1 ? pageUrl(path, page - 1) : null,
      label: '&laquo; Previous',
      page: page > 1 ? page - 1 : null,
      active: false,
    },
  ];

  for (const item of pages) {
    if (item === 'dots') {
      links.push({ url: null, label: '...', page: null, active: false });
    } else {
      links.push({
        url: pageUrl(path, item),
        label: String(item),
        page: item,
        active: item === page,
      });
    }
  }

  links.push({
    url: page < lastPage ? pageUrl(path, page + 1) : null,
    label: 'Next &raquo;',
    page: page < lastPage ? page + 1 : null,
    active: false,
  });

  return links;
}

export function paginate<T>(
  items: T[],
  total: number,
  page: number,
  path: string,
): Paginated<T> {
  const lastPage = Math.max(Math.ceil(total / PER_PAGE), 1);
  const from = items.length > 0 ? (page - 1) * PER_PAGE + 1 : null;
  const to = items.length > 0 ? (page - 1) * PER_PAGE + items.length : null;

  return {
    current_page: page,
    data: items,
    first_page_url: pageUrl(path, 1),
    from,
    last_page: lastPage,
    last_page_url: pageUrl(path, lastPage),
    links: buildLinks(path, page, lastPage),
    next_page_url: page < lastPage ? pageUrl(path, page + 1) : null,
    path,
    per_page: PER_PAGE,
    prev_page_url: page > 1 ? pageUrl(path, page - 1) : null,
    to,
    total,
  };
}
