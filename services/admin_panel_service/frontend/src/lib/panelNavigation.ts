interface NavigationItem {
  id: string;
}

export function isEducationPath(pathname: string): boolean {
  return pathname === "/admin-panel/education" || pathname.startsWith("/admin-panel/education/");
}

export function activeNavigationItem<T extends NavigationItem>(
  items: readonly T[], pathname: string, search: string,
): T | undefined {
  if (isEducationPath(pathname)) return items.find((item) => item.id === "education");
  const section = new URLSearchParams(search).get("section");
  const embeddedItems = items.filter((item) => item.id !== "education");
  // Resolve only against items permitted for the current user.
  return embeddedItems.find((item) => item.id === section) ?? embeddedItems[0];
}

export function panelSectionUrl(id: string): string {
  return id === "education"
    ? "/admin-panel/education"
    : `/admin-panel?${new URLSearchParams({ section: id })}`;
}
