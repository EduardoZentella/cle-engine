import { motion } from "motion/react";
import {
  ArrowRight,
  Languages,
  BrainCircuit,
  Globe,
  Activity,
  BookOpen,
  Sparkles,
  LogIn,
} from "lucide-react";
import type { AppPage, UserProfile } from "../types/app";

interface LandingPageProps {
  profile: UserProfile;
  apiHealthy: boolean;
  isLoggedIn: boolean;
  onNavigate: (page: AppPage) => void;
}

const features = [
  {
    title: "Contextual Translation",
    description:
      "Translates exactly to your real-world scenarios. We make sure whether you're at a fine-dining or a quick cafe, you sound perfectly natural.",
    icon: <Languages className="w-6 h-6 text-indigo-400" />,
    gradient: "from-indigo-500/20 to-blue-500/20",
  },
  {
    title: "Adaptive Practice",
    description:
      "Based on your latest translations, it generates dynamic flashcards and sentence builders tailored to your immediate needs.",
    icon: <BrainCircuit className="w-6 h-6 text-purple-400" />,
    gradient: "from-purple-500/20 to-fuchsia-500/20",
  },
  {
    title: "Cultural Nuance",
    description:
      "Never worry about sounding rude again. See different layers of politeness depending on the exact context and your level.",
    icon: <Globe className="w-6 h-6 text-teal-400" />,
    gradient: "from-teal-500/20 to-emerald-500/20",
  },
];

export function LandingPage({
  profile,
  apiHealthy,
  isLoggedIn,
  onNavigate,
}: LandingPageProps) {
  if (isLoggedIn) {
    return (
      <div className="w-full max-w-5xl mx-auto space-y-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-3xl border border-white/10 bg-linear-to-b from-indigo-950/40 to-black/40 backdrop-blur-xl p-8 sm:p-12"
        >
          <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-indigo-500/20 blur-3xl rounded-full pointer-events-none" />
          <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 bg-purple-500/20 blur-3xl rounded-full pointer-events-none" />

          <div className="relative z-10 grid gap-8 md:grid-cols-[1fr_auto] items-center">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-semibold uppercase tracking-wider text-indigo-300">
                <Sparkles className="w-3.5 h-3.5" /> Welcome back
              </div>
              <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-white">
                Hi, {profile.username}!
              </h1>
              <p className="text-lg text-white/60 max-w-xl leading-relaxed">
                You are currently building up your {profile.targetLanguage}{" "}
                skills in {profile.city}. Ready to keep honing your
                context-aware intuition?
              </p>
            </div>

            <div className="flex flex-col sm:flex-row md:flex-col gap-4">
              <button
                onClick={() => onNavigate("translation")}
                className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 rounded-full bg-indigo-600 font-semibold text-white transition-all hover:bg-indigo-500 hover:shadow-[0_0_30px_-5px_rgba(79,70,229,0.5)] overflow-hidden"
              >
                <div className="absolute inset-0 bg-linear-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" />
                <Languages className="w-5 h-5" />
                <span>Context Translate</span>
              </button>
              <button
                onClick={() => onNavigate("practice")}
                className="group inline-flex items-center justify-center gap-3 px-8 py-4 rounded-full bg-white/5 border border-white/10 font-semibold text-white transition-all hover:bg-white/10 hover:border-white/20"
              >
                <BookOpen className="w-5 h-5 opacity-70 group-hover:opacity-100 transition-opacity" />
                <span>Practice Skills</span>
              </button>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          <div className="rounded-3xl border border-white/10 bg-black/20 backdrop-blur-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-full bg-indigo-500/20 text-indigo-400">
                <Activity className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white/60">Current Level</h3>
            </div>
            <p className="text-3xl font-bold text-white">
              {profile.currentLevel.toUpperCase()}
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/20 backdrop-blur-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-full bg-purple-500/20 text-purple-400">
                <Globe className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white/60">Learning</h3>
            </div>
            <p className="text-3xl font-bold text-white">
              {profile.targetLanguage.toUpperCase()}
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/20 backdrop-blur-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-full bg-blue-500/20 text-blue-400">
                <Languages className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white/60">From</h3>
            </div>
            <p className="text-3xl font-bold text-white">
              {profile.baseLanguage.toUpperCase()}
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/20 backdrop-blur-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-full bg-teal-500/20 text-teal-400">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-teal-500"></span>
                </span>
                <span className="font-semibold text-white/60 ml-2">Status</span>
              </div>
            </div>
            <p className="text-xl font-bold text-white">
              Active in {profile.city}
            </p>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto space-y-24 pb-20">
      {/* Hero Section */}
      <section className="text-center space-y-8 mt-12 sm:mt-24">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-white/80"
        >
          <span className="relative flex h-2 w-2 mr-2">
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${apiHealthy ? "bg-emerald-400 animate-ping" : "bg-red-400"}`}
            ></span>
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${apiHealthy ? "bg-emerald-500" : "bg-red-500"}`}
            ></span>
          </span>
          System {apiHealthy ? "Online" : "Offline"}
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-transparent bg-clip-text bg-linear-to-br from-white to-white/60 max-w-4xl mx-auto leading-tight"
        >
          Master Languages <br className="hidden sm:block" /> Through Context.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-lg sm:text-xl text-white/60 max-w-2xl mx-auto leading-relaxed"
        >
          Learn faster with AI-powered recommendations based on real-world
          scenarios. Don't just translate, understand the culture and tone.
        </motion.p>
      </section>

      {/* Features Section */}
      <section className="grid sm:grid-cols-3 gap-6">
        {features.map((feature, index) => (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 + index * 0.1 }}
            className={`p-8 rounded-3xl border border-white/10 bg-linear-to-b ${feature.gradient} backdrop-blur-md space-y-4 shadow-xl`}
          >
            <div className="w-12 h-12 rounded-2xl bg-black/40 flex items-center justify-center shadow-inner border border-white/5">
              {feature.icon}
            </div>
            <h3 className="text-xl font-bold text-white tracking-tight">
              {feature.title}
            </h3>
            <p className="text-white/60 leading-relaxed text-sm">
              {feature.description}
            </p>
          </motion.div>
        ))}
      </section>

      {/* CTA Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-black/40 backdrop-blur-xl p-10 sm:p-16 text-center shadow-2xl"
      >
        <div className="absolute inset-0 bg-linear-to-tr from-indigo-500/10 via-transparent to-purple-500/10" />
        <div className="relative z-10 max-w-2xl mx-auto space-y-6">
          <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            Ready to Start Learning?
          </h2>
          <p className="text-lg text-white/60">
            Open the sidebar menu and enter your name to begin your personalized
            language learning experience without needing a formal account.
          </p>
          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            <div className="flex items-center gap-3 px-6 py-3 rounded-full bg-white/5 border border-white/10 text-white/80">
              <LogIn className="w-5 h-5 text-indigo-400" />
              <span>Use the menu top-left</span>
            </div>
            <ArrowRight className="hidden sm:block w-5 h-5 text-white/20" />
            <div className="flex items-center gap-3 px-6 py-3 rounded-full bg-white/5 border border-white/10 text-white/80">
              <Languages className="w-5 h-5 text-purple-400" />
              <span>Translate & Learn</span>
            </div>
          </div>
        </div>
      </motion.section>
    </div>
  );
}
