import { Activity, BarChart3, CalendarDays, LogOut, Settings } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/app/dashboard', label: 'Dashboard', icon: BarChart3, disabled: true },
  { to: '/app/weekly-outlook', label: 'Weekly Outlook', icon: CalendarDays, disabled: false },
  { to: '/app/activities', label: 'Activities', icon: Activity, disabled: true },
  { to: '/app/settings', label: 'Settings', icon: Settings, disabled: true },
];

export function AppLayout(): JSX.Element {
  const { logout, profile } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <div className="grid min-h-screen md:grid-cols-[250px_1fr]">
        <aside className="border-r bg-card/50 p-4 md:p-6">
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

        <div className="flex min-h-screen flex-col">
          <header className="border-b px-6 py-4">
            <div className="mx-auto flex w-full max-w-7xl items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Performance</p>
                <h2 className="text-xl font-semibold">Weekly planning</h2>
              </div>
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
