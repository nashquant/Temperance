import { BarChart3, CalendarDays, Database, LogOut, Settings } from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/app/dashboard', label: 'Dashboard', icon: BarChart3, disabled: false },
  { to: '/app/athlete-progression', label: 'Athlete Progression', icon: BarChart3, disabled: false },
  { to: '/app/week-planner', label: 'Week Planner', icon: CalendarDays, disabled: false },
  { to: '/app/data-extract', label: 'Data Extract', icon: Database, disabled: false },
  { to: '/app/settings', label: 'Settings', icon: Settings, disabled: false },
];

export function AppLayout(): JSX.Element {
  const { logout, profile } = useAuth();
  const location = useLocation();

  const headerMeta = (() => {
    const path = location.pathname;
    if (path.startsWith('/app/dashboard')) return { section: 'Performance', title: 'Dashboard' };
    if (path.startsWith('/app/athlete-progression')) return { section: 'Analytics', title: 'Athlete Progression' };
    if (path.startsWith('/app/week-planner')) return { section: 'Performance', title: 'Week Planner' };
    if (path.startsWith('/app/data-extract')) return { section: 'Data', title: 'Data Extract' };
    if (path.startsWith('/app/settings')) return { section: 'Configuration', title: 'Settings' };
    return { section: 'Performance', title: 'Temperance' };
  })();

  return (
    <div className="h-screen overflow-hidden bg-background">
      <div className="grid h-full md:grid-cols-[250px_1fr]">
        <aside className="sticky top-0 h-screen overflow-y-auto border-r bg-card/50 p-4 md:p-6">
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
            <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </Button>
          </div>
        </aside>

        <div className="flex h-screen min-h-0 flex-col overflow-hidden">
          <header className="sticky top-0 z-20 border-b bg-background/95 px-6 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
            <div className="mx-auto flex w-full max-w-7xl items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">{headerMeta.section}</p>
                <h2 className="text-xl font-semibold">{headerMeta.title}</h2>
              </div>
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
