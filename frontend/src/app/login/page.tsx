import type { Metadata } from 'next';

import { AuthForm } from '@/components/auth-form';

export const metadata: Metadata = {
  title: 'Sign in · SkillAtlas',
  description: 'Sign in to your SkillAtlas account.',
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-12">
      <AuthForm mode="login" next={next} />
    </div>
  );
}
