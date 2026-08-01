import type { Metadata } from 'next';

import { AuthForm } from '@/components/auth-form';

export const metadata: Metadata = {
  title: 'Create an account · SkillAtlas',
  description: 'Create a SkillAtlas account and get a roadmap built for your schedule.',
};

export default async function SignupPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-12">
      <AuthForm mode="signup" next={next} />
    </div>
  );
}
