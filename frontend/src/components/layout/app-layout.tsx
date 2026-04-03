import type { ReactNode } from 'react';
import { BarChart3, CalendarDays, ChevronLeft, ChevronRight, CircleHelp, Database, HeartPulse, LogOut, Menu, Settings, X } from 'lucide-react';
import { useEffect, useId, useState } from 'react';
import { NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/features/auth/hooks/use-auth';
import type { AuthSession, MeResponse } from '@/features/auth/types';
import { setGarminCredentials } from '@/features/data-extract/services/data-extract-api';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/app/dashboard', label: 'Dashboard', icon: BarChart3, disabled: false },
  { to: '/app/week-planner', label: 'Week Planner', icon: CalendarDays, disabled: false },
  { to: '/app/athlete-progression', label: 'Athlete Progression', icon: BarChart3, disabled: false },
  { to: '/app/wellness', label: 'Wellness', icon: HeartPulse, disabled: false },
  { to: '/app/data-extract', label: 'Data Extract', icon: Database, disabled: false },
  { to: '/app/settings', label: 'User Settings', icon: Settings, disabled: false },
  { to: '/app/about', label: 'About Temperance', icon: CircleHelp, disabled: false },
];

const headerMetaByPrefix: Array<{ prefix: string; section: string; title: string }> = [
  { prefix: '/app/dashboard', section: 'Performance', title: 'Dashboard' },
  { prefix: '/app/athlete-progression', section: 'Analytics', title: 'Athlete Progression' },
  { prefix: '/app/wellness', section: 'Recovery', title: 'Wellness' },
  { prefix: '/app/week-planner', section: 'Performance', title: 'Week Planner' },
  { prefix: '/app/data-extract', section: 'Data', title: 'Data Extract' },
  { prefix: '/app/settings', section: 'Configuration', title: 'Settings' },
  { prefix: '/app/about', section: 'About', title: 'About Temperance' },
];

const DESKTOP_NAV_STORAGE_KEY = 'temperance.desktop-nav-expanded';
const DEFAULT_PAGE_WIDTH_CLASS_NAME = 'max-w-7xl';

export interface AppLayoutOutletContext {
  setHeaderActions: (actions: ReactNode | null) => void;
  setPageWidthClassName: (className: string | null) => void;
}

export function useAppLayoutContext(): AppLayoutOutletContext {
  return useOutletContext<AppLayoutOutletContext>();
}

function getHeaderMeta(pathname: string): { section: string; title: string } {
  return (
    headerMetaByPrefix.find((item) => pathname.startsWith(item.prefix)) ?? {
      section: 'Performance',
      title: 'Temperance',
    }
  );
}

function NavigationLinks({ onNavigate, collapsed = false }: { onNavigate?: () => void; collapsed?: boolean }): JSX.Element {
  return (
    <nav aria-label="Primary navigation" className="space-y-1">
      {navItems.map((item) => {
        const Icon = item.icon;
        if (item.disabled) {
          return (
            <div
              key={item.label}
              title={collapsed ? item.label : undefined}
              className={cn(
                'flex items-center rounded-md px-3 py-2 text-sm text-muted-foreground',
                collapsed ? 'justify-center' : 'gap-2',
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {collapsed ? <span className="sr-only">{item.label}</span> : <span>{item.label}</span>}
            </div>
          );
        }

        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              cn(
                'flex items-center rounded-md px-3 py-2 text-sm transition-colors',
                collapsed ? 'justify-center' : 'gap-2',
                isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
              )
            }
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {collapsed ? <span className="sr-only">{item.label}</span> : <span>{item.label}</span>}
          </NavLink>
        );
      })}
    </nav>
  );
}

interface SessionPanelProps {
  logout: () => void;
  owners: string[];
  profile: MeResponse | null;
  session: AuthSession | null;
  switchingOwner: boolean;
  onOwnerChange: (owner: string) => void;
  collapsed?: boolean;
}

function SessionPanel({
  logout,
  owners,
  profile,
  session,
  switchingOwner,
  onOwnerChange,
  collapsed = false,
}: SessionPanelProps): JSX.Element {
  const ownerSelectId = useId();
  const showOwnerSwitcher = profile?.role === 'admin' && owners.length > 1;

  if (collapsed) {
    return (
      <div className="space-y-3">
        <Button
          variant="outline"
          size="icon"
          className="w-full"
          onClick={logout}
          disabled={!session}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3 text-xs text-muted-foreground">
      <div>
        <p className="font-medium text-foreground">Signed in as</p>
        <p>{profile?.user ?? 'Unknown user'}</p>
      </div>

      {showOwnerSwitcher ? (
        <div className="space-y-1.5">
          <Label htmlFor={ownerSelectId} className="text-xs font-medium text-foreground">
            Viewing owner
          </Label>
          <select
            id={ownerSelectId}
            value={profile.owner}
            onChange={(event) => onOwnerChange(event.target.value)}
            disabled={switchingOwner}
            className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
          >
            {owners.map((owner) => (
              <option key={owner} value={owner}>
                {owner}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <Button
        variant="outline"
        size="sm"
        className="w-full justify-start gap-2"
        onClick={logout}
        disabled={!session}
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        Sign out
      </Button>
    </div>
  );
}

export function AppLayout(): JSX.Element {
  const { logout, owners, profile, session, setOwner } = useAuth();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [switchingOwner, setSwitchingOwner] = useState(false);
  const [desktopNavExpanded, setDesktopNavExpanded] = useState(false);
  const [headerActions, setHeaderActions] = useState<ReactNode | null>(null);
  const [pageWidthClassName, setPageWidthClassName] = useState(DEFAULT_PAGE_WIDTH_CLASS_NAME);
  const headerMeta = getHeaderMeta(location.pathname);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = window.localStorage.getItem(DESKTOP_NAV_STORAGE_KEY);
    if (saved === 'expanded') {
      setDesktopNavExpanded(true);
      return;
    }
    if (saved === 'collapsed') {
      setDesktopNavExpanded(false);
      return;
    }
    setDesktopNavExpanded(window.innerWidth >= 1280);
  }, []);

  const handleOwnerChange = async (nextOwner: string) => {
    if (!profile || !session?.token) {
      setOwner(nextOwner);
      return;
    }
    if (nextOwner === profile.owner) return;

    try {
      setSwitchingOwner(true);
      await setGarminCredentials({
        token: session.token,
        owner: profile.owner,
        payload: { email: '', password: '' },
      });
    } catch {
      // Swallow credential-clear failures so owner switching still works.
    } finally {
      setOwner(nextOwner);
      setSwitchingOwner(false);
    }
  };

  const toggleDesktopNav = () => {
    const next = !desktopNavExpanded;
    setDesktopNavExpanded(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(DESKTOP_NAV_STORAGE_KEY, next ? 'expanded' : 'collapsed');
    }
  };

  return (
    <div className="h-[100dvh] overflow-hidden bg-background">
      <a
        href="#app-main-content"
        className="sr-only absolute left-4 top-4 z-[60] rounded-md bg-background px-3 py-2 text-sm font-medium text-foreground shadow-lg focus:not-sr-only focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Skip to main content
      </a>
      <div className="h-[100dvh]">
        <aside
          className={cn(
            'fixed inset-y-0 left-0 z-20 hidden overflow-y-auto border-r bg-card/50 transition-[width,padding] duration-200 lg:block',
            desktopNavExpanded ? 'w-[236px] p-5' : 'w-[72px] p-3',
          )}
        >
          <div className={cn('mb-6 flex items-center justify-between', desktopNavExpanded ? '' : 'justify-center')}>
            {desktopNavExpanded ? <h1 className="text-lg font-semibold">Temperance</h1> : <h1 className="text-lg font-semibold">T</h1>}
          </div>
          <NavigationLinks collapsed={!desktopNavExpanded} />
          <Separator className="my-4" />
          <SessionPanel
            logout={logout}
            owners={owners}
            profile={profile}
            session={session}
            switchingOwner={switchingOwner}
            onOwnerChange={(owner) => void handleOwnerChange(owner)}
            collapsed={!desktopNavExpanded}
          />
        </aside>

        {mobileNavOpen ? (
          <div
            className="fixed inset-0 z-50 lg:hidden"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
          >
            <button
              type="button"
              className="absolute inset-0 bg-black/55"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close navigation"
            />
            <aside className="relative h-full w-[85vw] max-w-[300px] overflow-y-auto overscroll-contain border-r bg-card/95 p-4 shadow-2xl backdrop-blur">
              <div className="mb-6 flex items-center justify-between">
                <h1 className="text-lg font-semibold">Temperance</h1>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setMobileNavOpen(false)}
                  aria-label="Close navigation"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </Button>
              </div>
              <NavigationLinks onNavigate={() => setMobileNavOpen(false)} />
              <Separator className="my-4" />
              <SessionPanel
                logout={logout}
                owners={owners}
                profile={profile}
                session={session}
                switchingOwner={switchingOwner}
                onOwnerChange={(owner) => void handleOwnerChange(owner)}
              />
            </aside>
          </div>
        ) : null}

        <div
          className={cn(
            'flex h-[100dvh] min-w-0 flex-col overflow-y-auto transition-[padding] duration-200',
            desktopNavExpanded ? 'lg:pl-[236px]' : 'lg:pl-[72px]',
          )}
        >
          <header className="sticky top-0 z-30 border-b bg-background/95 px-3 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 sm:px-6 sm:py-4">
            <div className={cn('mx-auto flex w-full items-center justify-between gap-3', pageWidthClassName)}>
              <div className="flex min-w-0 items-center gap-3">
                <Button
                  variant="outline"
                  size="icon"
                  className="hidden lg:inline-flex"
                  onClick={toggleDesktopNav}
                  aria-label={desktopNavExpanded ? 'Collapse navigation' : 'Expand navigation'}
                  title={desktopNavExpanded ? 'Collapse navigation' : 'Expand navigation'}
                >
                  {desktopNavExpanded ? <ChevronLeft className="h-5 w-5" aria-hidden="true" /> : <ChevronRight className="h-5 w-5" aria-hidden="true" />}
                </Button>
                <div className="min-w-0">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">{headerMeta.section}</p>
                  <h2 className="truncate text-lg font-semibold sm:text-xl">{headerMeta.title}</h2>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {headerActions ? <div className="flex items-center gap-2">{headerActions}</div> : null}
                <Button
                  variant="outline"
                  size="icon"
                  className="lg:hidden"
                  onClick={() => setMobileNavOpen(true)}
                  aria-label="Open navigation"
                >
                  <Menu className="h-5 w-5" aria-hidden="true" />
                </Button>
              </div>
            </div>
          </header>
          <main id="app-main-content" tabIndex={-1} className="min-h-0 flex-1">
            <div className={cn('mx-auto w-full px-3 py-4 sm:px-6 sm:py-6', pageWidthClassName)}>
              <Outlet
                context={{
                  setHeaderActions,
                  setPageWidthClassName: (className: string | null) =>
                    setPageWidthClassName(className || DEFAULT_PAGE_WIDTH_CLASS_NAME),
                }}
              />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
