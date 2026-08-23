"use client";

import React, { useRef, useState } from 'react';
import Link from 'next/link';
import {
  motion,
  useScroll,
  useTransform,
  AnimatePresence,
  type Variants,
} from 'framer-motion';
import {
  ArrowRight,
  BookOpen,
  Map,
  GitBranch,
  MessageSquareQuote,
  Route,
  Sparkles,
  ChevronDown,
  Target,
  Users,
  Zap,
  Award
} from 'lucide-react';

import { ButtonLink } from '@/components/button-link';
import GalleryHoverCarousel from '@/components/ui/gallery-hover-carousel';
import { SlidingPuzzle } from '@/components/ui/sliding-puzzle';
import type { Domain, TrackSummary, User } from '@/lib/types';
import { SterlingGateKineticNavigation } from '@/components/ui/sterling-gate-kinetic-navigation';

import { ThemeToggle } from '@/components/theme-toggle';

// Framer Motion Variants.
//
// The `Variants` annotation is load-bearing: without it TypeScript widens
// `type: "spring"` to `string`, which does not satisfy `AnimationGeneratorType`
// and fails the build. Annotating gives the literal a contextual type.
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.2,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 70, damping: 20 }
  },
};

const stepContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.1 },
  },
};

const stepVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 60 } },
};

export function LandingPageInteractive({
  domains,
  tracks,
  conceptCount,
  featured,
  user,
}: {
  domains: Domain[];
  tracks: TrackSummary[];
  conceptCount: number;
  featured: TrackSummary[];
  /** Signed-in visitor, or null. Only the nav uses it, to greet by name
   *  instead of offering a sign-in link they do not need. */
  user?: User | null;
}) {
  const { scrollYProgress } = useScroll();
  const heroY = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  return (
    // overflow-x-hidden: the decorative hero glow is a fixed 820px wide and
    // the footer nav does not wrap, so both push the document wider than a
    // phone viewport and give the whole page a horizontal scrollbar.
    <div className="flex min-h-screen flex-col overflow-x-hidden">
      <SterlingGateKineticNavigation user={user} />

      <main className="flex-1 overflow-hidden">
        {/* --- hero ------------------------------------------------------ */}
        <section className="relative border-b min-h-screen flex flex-col pt-16 lg:pt-24 pb-20">
          <div className="contour pointer-events-none absolute inset-0 opacity-50 dark:opacity-30" aria-hidden />
          <motion.div
            style={{ y: heroY, opacity: heroOpacity }}
            className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]"
            aria-hidden
          />

          <motion.div 
            className="relative w-full px-8 md:px-16 lg:px-24"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-12 lg:gap-16 items-start">
              <div className="lg:col-span-3 max-w-2xl">
                <motion.p variants={itemVariants} className="eyebrow flex items-center gap-2">
                  <Map className="h-4 w-4 text-primary" />
                  <span className="font-bold text-foreground mr-1 uppercase tracking-widest text-xs">SkillAtlas</span>
                  <span className="opacity-50">/</span>
                  A survey of everything worth learning
                </motion.p>

                <motion.h1 variants={itemVariants} className="mt-6 font-display text-4xl leading-[1.05] font-semibold sm:text-5xl lg:text-6xl xl:text-7xl">
                  <span className="whitespace-nowrap">Every skill has a map.</span>
                  <span className="block text-primary italic mt-2">Most people study without one.</span>
                </motion.h1>

                <motion.p variants={itemVariants} className="mt-7 text-lg leading-relaxed text-muted-foreground">
                  SkillAtlas charts {conceptCount} concepts across {domains.length} domains
                  into a prerequisite graph, then plots the shortest honest route from
                  where you are to the role you want — paced to the hours you actually
                  have.
                </motion.p>

                <motion.div variants={itemVariants} className="mt-10 flex flex-col gap-6 sm:flex-row">
                  <ButtonLink size="lg" href="/explore" className="h-11 px-6 relative overflow-hidden group">
                    <span className="relative z-10 flex items-center gap-2">
                      Browse the atlas
                      <ArrowRight className="transition-transform group-hover:translate-x-1" />
                    </span>
                    <div className="absolute inset-0 bg-primary/10 transform translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                  </ButtonLink>
                  <ButtonLink size="lg" variant="outline" href="/companies" className="h-11 px-6 hover:bg-muted/50 transition-colors">
                    Companies
                  </ButtonLink>
                </motion.div>

                <motion.dl variants={itemVariants} className="mt-16 grid grid-cols-3 gap-6 border-t pt-8">
                  <Stat value={domains.length} label="domains charted" />
                  <Stat value={tracks.length} label="career routes" />
                  <Stat value={conceptCount} label="concepts written" />
                </motion.dl>
              </div>
              
              <div className="hidden lg:block lg:col-span-2 lg:mt-8">
                 <motion.div variants={itemVariants}>
                    <SlidingPuzzle />
                 </motion.div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* --- how it works ---------------------------------------------- */}
        <section className="border-b relative">
          <div className="w-full px-8 py-24 md:px-16 lg:px-24">
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.6 }}
            >
              <p className="eyebrow">How it works</p>
              <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold text-balance sm:text-4xl">
                Four things most learning sites leave to you
              </h2>
            </motion.div>

            <motion.div 
              className="mt-16 grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2 lg:grid-cols-4"
              variants={stepContainerVariants}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-50px" }}
            >
              <Step
                index="01"
                icon={<GitBranch className="h-5 w-5" />}
                title="Order that holds"
                body="Concepts are nodes and prerequisites are edges. A topological sort guarantees nothing is scheduled before the thing it depends on."
              />
              <Step
                index="02"
                icon={<Route className="h-5 w-5" />}
                title="Paced to your week"
                body="Tell us your daily hours. The route is packed into weeks against that budget, and shortened by whatever you already know."
              />
              <Step
                index="03"
                icon={<BookOpen className="h-5 w-5" />}
                title="Written, not linked"
                body="Every concept has an explainer, hand-picked resources, a graded quiz, and the interview questions it tends to attract."
              />
              <Step
                index="04"
                icon={<MessageSquareQuote className="h-5 w-5" />}
                title="A tutor with context"
                body="Ask anything. It answers from the concept notes and from your actual progress — and tells you when it does not know."
              />
            </motion.div>
          </div>
        </section>

        {/* --- tracks marquees ------------------------------------------------------ */}
        <div className="border-b bg-card/5 border-t py-20 overflow-hidden flex flex-col gap-6 relative">
          <div className="px-8 md:px-16 lg:px-24 mb-4">
            <h2 className="font-display text-3xl font-semibold">Available destinations</h2>
          </div>
          
          {/* Row 1: Left to Right */}
          <div className="relative flex w-full py-4">
            <div className="flex animate-marquee-reverse whitespace-nowrap min-w-full">
              {[...tracks, ...tracks].map((track, i) => (
                <div key={`r1-${track.slug}-${i}`} className="inline-flex flex-col justify-center rounded-2xl border border-white/5 bg-background/40 backdrop-blur-xl p-6 mx-3 w-[350px] whitespace-normal flex-shrink-0 shadow-lg relative overflow-hidden group">
                  <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                  <h3 className="font-display text-lg font-semibold relative z-10">{track.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground line-clamp-2 relative z-10">{track.description}</p>
                  <div className="mt-4 flex items-center gap-2 text-xs font-medium text-muted-foreground relative z-10">
                    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-primary">{track.concept_count} concepts</span>
                    <span>~{track.total_hours}h</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Row 2: Right to Left */}
          <div className="relative flex w-full py-4">
            <div className="flex animate-marquee whitespace-nowrap min-w-full">
              {[...tracks, ...tracks].reverse().map((track, i) => (
                <div key={`r2-${track.slug}-${i}`} className="inline-flex flex-col justify-center rounded-2xl border border-white/5 bg-background/40 backdrop-blur-xl p-6 mx-3 w-[350px] whitespace-normal flex-shrink-0 shadow-lg relative overflow-hidden group">
                  <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                  <h3 className="font-display text-lg font-semibold relative z-10">{track.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground line-clamp-2 relative z-10">{track.description}</p>
                  <div className="mt-4 flex items-center gap-2 text-xs font-medium text-muted-foreground relative z-10">
                    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-primary">{track.concept_count} concepts</span>
                    <span>~{track.total_hours}h</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Gradient masks for smooth edges */}
          <div className="pointer-events-none absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-background to-transparent z-10" />
          <div className="pointer-events-none absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-background to-transparent z-10" />
        </div>

        {/* --- features bento --------------------------------------------- */}
        <section className="border-b relative">
          <div className="w-full px-8 py-24 md:px-16 lg:px-24">
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6 }}
            >
              <p className="eyebrow">Platform Highlights</p>
              <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold text-balance sm:text-4xl">
                Built for the ambitious and self-taught
              </h2>
            </motion.div>

            <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4">
              <motion.div 
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ delay: 0.1 }}
                className="md:col-span-2"
              >
                <BentoFeature 
                  title="Dynamic Prerequisite Graph" 
                  description="Unlike rigid video courses, SkillAtlas builds a bespoke curriculum based on the nodes you actually need to learn, skipping what you already know." 
                  icon={<Target />} 
                  className="h-full"
                />
              </motion.div>
              <motion.div 
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ delay: 0.2 }}
                className="md:col-span-1"
              >
                <BentoFeature 
                  title="Time-Paced" 
                  description="Your curriculum is sliced precisely into weekly sprints matching the hours you have available." 
                  icon={<Zap />} 
                  className="h-full"
                />
              </motion.div>
              <motion.div 
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ delay: 0.3 }}
                className="md:col-span-1"
              >
                <BentoFeature 
                  title="Verified Credentials" 
                  description="Complete a route and earn cryptographically verified credentials that prove your knowledge to employers." 
                  icon={<Award />} 
                  className="h-full"
                />
              </motion.div>
              <motion.div 
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ delay: 0.4 }}
                className="md:col-span-2"
              >
                <BentoFeature 
                  title="Vibrant Community" 
                  description="You are never learning alone. Discuss concepts, share projects, and get unblocked by thousands of other self-taught engineers." 
                  icon={<Users />} 
                  className="h-full"
                />
              </motion.div>
            </div>
          </div>
        </section>

        {/* --- faq -------------------------------------------------------- */}
        <section className="border-b relative bg-card/10">
          <div className="w-full px-8 py-24 md:px-16 lg:px-24">
             <div className="mx-auto max-w-3xl">
                <motion.div 
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-50px" }}
                  transition={{ duration: 0.6 }}
                  className="text-center mb-16"
                >
                  <p className="eyebrow">FAQ</p>
                  <h2 className="mt-3 font-display text-3xl font-semibold sm:text-4xl">
                    Common questions
                  </h2>
                </motion.div>
                
                <div className="flex flex-col gap-2">
                  <FaqItem 
                    question="Is SkillAtlas free to use?" 
                    answer="Yes, exploring the prerequisite graph and generating career routes is entirely free. Premium features like contextual AI tutoring and verified credentials require a subscription."
                  />
                  <FaqItem 
                    question="How is this different from a bootcamp?" 
                    answer="Bootcamps are expensive and rigid. SkillAtlas uses a topological sort to map out the exact sequence of concepts you need for a specific role, entirely paced to your own schedule, for a fraction of the cost."
                  />
                  <FaqItem 
                    question="What if I already know some of the concepts?" 
                    answer="During onboarding, you can check off the skills you already possess. Our engine will prune those nodes (and their satisfied dependencies) from your route, saving you time."
                  />
                  <FaqItem 
                    question="Are the learning resources up to date?" 
                    answer="Yes, our hand-picked resources are continuously community-vetted and updated by industry experts to ensure you're always learning modern best practices."
                  />
                </div>
             </div>
          </div>
        </section>

        {/* --- closing ---------------------------------------------------- */}
        <section className="relative overflow-hidden py-32">
          <div className="contour pointer-events-none absolute inset-0 opacity-40 dark:opacity-20" aria-hidden />
          <motion.div 
            className="relative w-full px-8 text-center md:px-16 lg:px-24"
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: "easeOut" }}
          >
            <Sparkles className="mx-auto h-8 w-8 text-primary" />
            <h2 className="mt-6 font-display text-4xl font-semibold text-balance sm:text-5xl">
              Stop collecting bookmarks. Start covering ground.
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-lg text-muted-foreground leading-relaxed">
              Pick a domain, set the pace you can actually keep, and get a route where
              every step ends in something you built. It takes about two minutes.
            </p>
            <ButtonLink size="lg" href="/explore" className="mt-10 h-12 px-8 text-base shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
              Choose your domain
              <ArrowRight className="ml-2 h-5 w-5" />
            </ButtonLink>
          </motion.div>
        </section>
      </main>

      <footer className="border-t bg-background/50">
        <div className="w-full flex flex-wrap items-center justify-between gap-4 px-8 py-10 text-sm text-muted-foreground md:px-16 lg:px-24">
          <p className="font-medium">© {new Date().getFullYear()} SkillAtlas</p>
          <nav className="flex flex-wrap items-center gap-x-6 gap-y-2" aria-label="Footer">
            <Link href="/explore" className="inline-flex min-h-[24px] items-center hover:text-foreground transition-colors">
              Explore
            </Link>
            <Link href="/companies" className="inline-flex min-h-[24px] items-center hover:text-foreground transition-colors">
              Companies
            </Link>
            <Link href="/projects" className="inline-flex min-h-[24px] items-center hover:text-foreground transition-colors">
              Projects
            </Link>
            <Link href="/community" className="inline-flex min-h-[24px] items-center hover:text-foreground transition-colors">
              Community
            </Link>
            <div className="ml-4 pl-4 border-l border-border/50">
              <ThemeToggle />
            </div>
          </nav>
        </div>
      </footer>
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <dt className="font-display text-4xl font-bold tabular-nums tracking-tight">{value}</dt>
      <dd className="mt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground/80">{label}</dd>
    </div>
  );
}

function Step({
  index,
  icon,
  title,
  body,
}: {
  index: string;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <motion.div variants={stepVariants} className="bg-background p-8 hover:bg-muted/30 transition-colors duration-500">
      <div className="flex items-center justify-between">
        <span className="text-primary">{icon}</span>
        <span className="font-mono text-xs font-bold text-muted-foreground/60">{index}</span>
      </div>
      <h3 className="mt-6 font-display text-xl font-semibold tracking-tight">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{body}</p>
    </motion.div>
  );
}

function BentoFeature({ title, description, icon, className = "" }: { title: string, description: string, icon: React.ReactNode, className?: string }) {
  return (
    <div className={`group relative overflow-hidden rounded-2xl border bg-card p-8 transition-all hover:bg-accent ${className}`}>
      <div className="absolute -right-4 -top-4 opacity-5 transition-transform duration-500 group-hover:scale-110 group-hover:opacity-10">
        {/* React 19 types default ReactElement's props to `unknown`, so the
            prop being overridden has to be named for cloneElement to accept it. */}
        {React.cloneElement(icon as React.ReactElement<{ className?: string }>, {
          className: "w-48 h-48",
        })}
      </div>
      <div className="relative z-10 flex h-full flex-col justify-between">
        <div className="mb-8 w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
        <div>
          <h3 className="font-display text-2xl font-semibold mb-2">{title}</h3>
          <p className="text-muted-foreground leading-relaxed">{description}</p>
        </div>
      </div>
    </div>
  )
}

function FaqItem({ question, answer }: { question: string, answer: string }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="border-b py-4">
      <button 
        onClick={() => setIsOpen(!isOpen)} 
        className="flex w-full items-center justify-between py-4 text-left font-display text-xl font-semibold hover:text-primary transition-colors cursor-none"
      >
        {question}
        <motion.div animate={{ rotate: isOpen ? 180 : 0 }}>
          <ChevronDown className="h-5 w-5" />
        </motion.div>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <p className="pb-6 text-muted-foreground leading-relaxed pt-2">{answer}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
