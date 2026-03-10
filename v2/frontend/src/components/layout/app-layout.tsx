import { BarChart3, CalendarDays, Database, HeartPulse, LogOut, Menu, Settings, X } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { setGarminCredentials } from '@/features/data-extract/services/data-extract-api';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/app/dashboard', label: 'Dashboard', icon: BarChart3, disabled: false },
  { to: '/app/week-planner', label: 'Week Planner', icon: CalendarDays, disabled: false },
  { to: '/app/athlete-progression', label: 'Athlete Progression', icon: BarChart3, disabled: false },
  { to: '/app/wellness', label: 'Wellness', icon: HeartPulse, disabled: false },
  { to: '/app/data-extract', label: 'Data Extract', icon: Database, disabled: false },
  { to: '/app/settings', label: 'User Settings', icon: Settings, disabled: false },
];

export function AppLayout(): JSX.Element {
  const { logout, owners, profile, session, setOwner } = useAuth();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [switchingOwner, setSwitchingOwner] = useState(false);

  const headerMeta = (() => {
    const path = location.pathname;
    if (path.startsWith('/app/dashboard')) return { section: 'Performance', title: 'Dashboard' };
    if (path.startsWith('/app/athlete-progression')) return { section: 'Analytics', title: 'Athlete Progression' };
    if (path.startsWith('/app/wellness')) return { section: 'Recovery', title: 'Wellness' };
    if (path.startsWith('/app/week-planner')) return { section: 'Performance', title: 'Week Planner' };
    if (path.startsWith('/app/data-extract')) return { section: 'Data', title: 'Data Extract' };
    if (path.startsWith('/app/settings')) return { section: 'Configuration', title: 'Settings' };
    return { section: 'Performance', title: 'Temperance' };
  })();

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
    <div className="h-screen overflow-hidden bg-background">
      <div className="grid h-full md:grid-cols-[250px_1fr]">
        <aside className="sticky top-0 hidden h-screen overflow-y-auto border-r bg-card/50 p-4 md:block md:p-6">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-lg font-semibold">Temperance</h1>
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              if (item.disabled) {
                return (
                  <div key={item.label} className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground">
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </div>
                );
              }

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                      isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
          <Separator className="my-4" />
          <div className="space-y-3 text-xs text-muted-foreground">
            <div>
              <p className="font-medium text-foreground">Signed in as</p>
              <p>{profile?.user ?? 'Unknown user'}</p>
            </div>
            {profile?.role === 'admin' && owners.length > 1 ? (
              <div className="space-y-1.5">
                <p className="font-medium text-foreground">Viewing owner</p>
                <select
                  value={profile.owner}
                  onChange={(event) => void handleOwnerChange(event.target.value)}
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
            <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </Button>
          </div>
        </aside>

        {mobileNavOpen ? (
          <div className="fixed inset-0 z-50 md:hidden">
            <button
              type="button"
              className="absolute inset-0 bg-black/55"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close navigation"
            />
            <aside className="relative h-full w-[260px] overflow-y-auto border-r bg-card/95 p-4 shadow-2xl backdrop-blur">
              <div className="mb-6 flex items-center justify-between">
                <h1 className="text-lg font-semibold">Temperance</h1>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setMobileNavOpen(false)}
                  aria-label="Close navigation"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <nav className="space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  if (item.disabled) {
                    return (
                      <div key={item.label} className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground">
                        <Icon className="h-4 w-4" />
                        <span>{item.label}</span>
                      </div>
                    );
                  }

                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      onClick={() => setMobileNavOpen(false)}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                          isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
                        )
                      }
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </nav>
              <Separator className="my-4" />
              <div className="space-y-3 text-xs text-muted-foreground">
                <div>
                  <p className="font-medium text-foreground">Signed in as</p>
                  <p>{profile?.user ?? 'Unknown user'}</p>
                </div>
                {profile?.role === 'admin' && owners.length > 1 ? (
                  <div className="space-y-1.5">
                    <p className="font-medium text-foreground">Viewing owner</p>
                    <select
                      value={profile.owner}
                      onChange={(event) => void handleOwnerChange(event.target.value)}
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
                <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={logout}>
                  <LogOut className="h-4 w-4" />
                  Sign out
                </Button>
              </div>
            </aside>
          </div>
        ) : null}

        <div className="flex h-screen min-h-0 flex-col overflow-hidden">
          <header className="sticky top-0 z-20 border-b bg-background/95 px-6 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
            <div className="mx-auto flex w-full max-w-7xl items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">{headerMeta.section}</p>
                <h2 className="text-xl font-semibold">{headerMeta.title}</h2>
              </div>
              <Button
                variant="outline"
                size="icon"
                className="md:hidden"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </div>
          </header>
          <main className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-7xl px-6 py-6">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
