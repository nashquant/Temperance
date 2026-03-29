import { BarChart3, CalendarDays, CircleHelp, Database, HeartPulse, LogOut, Menu, Settings, X } from 'lucide-react';
import { useId, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

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

function getHeaderMeta(pathname: string): { section: string; title: string } {
  return (
    headerMetaByPrefix.find((item) => pathname.startsWith(item.prefix)) ?? {
      section: 'Performance',
      title: 'Temperance',
    }
  );
}

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }): JSX.Element {
  return (
    <nav aria-label="Primary navigation" className="space-y-1">
      {navItems.map((item) => {
        const Icon = item.icon;
        if (item.disabled) {
          return (
            <div key={item.label} className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground">
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span>{item.label}</span>
            </div>
          );
        }

        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
              )
            }
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            <span>{item.label}</span>
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
}

function SessionPanel({
  logout,
  owners,
  profile,
  session,
  switchingOwner,
  onOwnerChange,
}: SessionPanelProps): JSX.Element {
  const ownerSelectId = useId();
  const showOwnerSwitcher = profile?.role === 'admin' && owners.length > 1;

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
            className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
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
  const headerMeta = getHeaderMeta(location.pathname);

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

  return (
    <div className="h-[100dvh] overflow-hidden bg-background">
      <a
        href="#app-main-content"
        className="sr-only absolute left-4 top-4 z-[60] rounded-md bg-background px-3 py-2 text-sm font-medium text-foreground shadow-lg focus:not-sr-only focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Skip to main content
      </a>
      <div className="h-[100dvh]">
        <aside className="fixed inset-y-0 left-0 z-20 hidden w-[250px] overflow-y-auto border-r bg-card/50 p-4 md:block md:p-6">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-lg font-semibold">Temperance</h1>
          </div>
          <NavigationLinks />
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

        {mobileNavOpen ? (
          <div
            className="fixed inset-0 z-50 md:hidden"
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

        <div className="flex h-[100dvh] min-w-0 flex-col overflow-y-auto md:pl-[250px]">
          <header className="sticky top-0 z-30 border-b bg-background/95 px-3 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 sm:px-6 sm:py-4">
            <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">{headerMeta.section}</p>
                <h2 className="truncate text-lg font-semibold sm:text-xl">{headerMeta.title}</h2>
              </div>
              <Button
                variant="outline"
                size="icon"
                className="md:hidden"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </Button>
            </div>
          </header>
          <main id="app-main-content" tabIndex={-1} className="min-h-0 flex-1">
            <div className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-6 sm:py-6">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
