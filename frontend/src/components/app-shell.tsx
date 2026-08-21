import Link from 'next/link';

import { SidebarNav } from '@/components/sidebar-nav';
import { ThemeToggle } from '@/components/theme-toggle';
import { TutorLauncher, type TutorContext } from '@/components/tutor-launcher';
import { UserBadgeStrip } from '@/components/user-menu';
import { getCurrentUser } from '@/lib/dal';
import {
  SidebarProvider,
  SidebarRoot,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarTrigger,
} from '@/components/lightswind/sidebar';

/**
 * The signed-in application frame: a fixed cartographic sidebar on large
 * screens, a compact drawer below that.
 *
 * The session is read here rather than in each page so the chrome renders
 * once, and pages stay focused on their own data.
 *
 * The AI helper is mounted here too, for the same reason: one helper that
 * follows the learner around beats a copy pasted onto each page that wants it,
 * and the ones that forgot going without. Pages that know where they are pass
 * `tutorContext`; the rest fall back to the launcher's own reading of the path.
 */
export async function AppShell({
  children,
  tutorContext,
}: {
  children: React.ReactNode;
  tutorContext?: TutorContext;
}) {
  const user = await getCurrentUser();

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <a href="#main-content" className="skip-link">
          Skip to content
        </a>
        <SidebarRoot>
          <SidebarHeader className="py-5 px-5 h-auto border-b border-sidebar-border">
            <div className="flex items-center justify-between">
              <Link href="/" className="group flex items-baseline gap-2">
                <span className="font-display text-xl leading-none font-semibold">
                  Skill<span className="text-primary">Atlas</span>
                </span>
              </Link>
              <SidebarTrigger className="static bg-transparent border-none shadow-none hover:bg-white/5" />
            </div>
            <p className="eyebrow mt-2">Chart your route</p>
          </SidebarHeader>

          <SidebarContent>
            <SidebarNav />
          </SidebarContent>

          <SidebarFooter className="space-y-3 border-t border-sidebar-border px-4 py-4">
            {user && <UserBadgeStrip user={user} />}
            <ThemeToggle className="w-full justify-center" />
          </SidebarFooter>
        </SidebarRoot>

        {/* `tabIndex={-1}` so the skip link can actually move focus here;
            without it the browser scrolls but focus stays in the sidebar and
            the next Tab goes back to nav item two. */}
        <div id="main-content" tabIndex={-1} className="flex min-w-0 flex-1 flex-col relative">
          <div className="absolute top-5 left-5 z-40">
             <SidebarTrigger hiddenOnExpand className="bg-card/80 backdrop-blur-md border border-white/10 shadow-xl rounded-full" />
          </div>
          {children}
        </div>

        <TutorLauncher context={tutorContext} signedIn={Boolean(user)} />
      </div>
    </SidebarProvider>
  );
}
