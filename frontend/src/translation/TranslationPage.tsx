import { useMemo, useState, useEffect, type SubmitEvent } from "react";
import { RecommendationSection } from "../recommendations/RecommendationSection";
import {
  generateRecommendations,
  requestTranslation,
  type RecommendationItem,
} from "../services/api";
import type { AppPage, PracticeSeed, UserProfile } from "../types/app";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import { Label } from "../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Card } from "../../components/ui/card";
import { Loader2, Languages, ArrowRight, BookOpen } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

const PRACTICE_SEED_STORAGE_KEY = "cle_engine_latest_practice_seed";

interface TranslationPageProps {
  userId: string;
  profile: UserProfile;
  onPredictedLevel: (level: string) => void;
  onNavigate: (page: AppPage) => void;
}

interface ContextScenario {
  id: string;
  label: string;
  context: {
    location: string;
    environment: string;
    sentiment: string;
    intent: string;
  };
}

interface FormValues {
  originalText: string;
  contextScenario: string;
}

const contextScenarios: ContextScenario[] = [
  {
    id: "casual",
    label: "Casual Conversation",
    context: {
      location: "Berlin",
      environment: "street",
      sentiment: "friendly",
      intent: "socialize",
    },
  },
  {
    id: "meeting",
    label: "School",
    context: {
      location: "school",
      environment: "classroom",
      sentiment: "focused",
      intent: "learn",
    },
  },
  {
    id: "travel",
    label: "Travel Situation",
    context: {
      location: "airport",
      environment: "public",
      sentiment: "neutral",
      intent: "inform",
    },
  },
  {
    id: "shopping",
    label: "Shopping",
    context: {
      location: "store",
      environment: "retail",
      sentiment: "neutral",
      intent: "transact",
    },
  },
  {
    id: "restaurant",
    label: "Restaurant",
    context: {
      location: "restaurant",
      environment: "dining",
      sentiment: "pleasant",
      intent: "order",
    },
  },
];

const initialForm = (): FormValues => ({
  originalText: "",
  contextScenario: "casual",
});

export function TranslationPage({
  userId,
  profile,
  onPredictedLevel,
  onNavigate,
}: TranslationPageProps) {
  const [form, setForm] = useState<FormValues>(initialForm);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>(
    [],
  );
  const [translation, setTranslation] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  // Listen for text passed from the auth safeguard
  useEffect(() => {
    const pendingText = sessionStorage.getItem("cle_pending_translation");

    if (pendingText) {
      setForm((prev) => ({
        ...prev,
        originalText: pendingText,
      }));

      // Clear it out so it doesn't accidentally trigger again later
      sessionStorage.removeItem("cle_pending_translation");
    }
  }, []);

  const selectedScenario: ContextScenario = useMemo(() => {
    const foundScenario = contextScenarios.find(
      (scenario) => scenario.id === form.contextScenario,
    );
    return foundScenario ?? contextScenarios[0];
  }, [form.contextScenario]);

  const storePracticeSeed = (
    originalText: string,
    translatedText: string,
    generatedRecommendations: RecommendationItem[],
  ) => {
    const practiceSeed: PracticeSeed = {
      originalText,
      translation: translatedText,
      sourceLanguage: profile.baseLanguage,
      targetLanguage: profile.targetLanguage,
      currentLevel: profile.currentLevel,
      contextLabel: selectedScenario.label,
      recommendations: generatedRecommendations.map((item) => item.text),
      generatedAt: new Date().toISOString(),
    };

    sessionStorage.setItem(
      PRACTICE_SEED_STORAGE_KEY,
      JSON.stringify(practiceSeed),
    );
  };

  const onSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();

    const originalText = form.originalText.trim();
    if (!originalText) {
      setError("Please provide the text you want to translate.");
      return;
    }

    setIsSubmitting(true);
    setError("");
    setTranslation("");
    setRecommendations([]);

    try {
      let translationResult = "";
      try {
        const transResponse = await requestTranslation({
          original_text: originalText,
          source_language: profile.baseLanguage,
          target_language: profile.targetLanguage,
          user_level: profile.currentLevel,
        });
        translationResult = transResponse.translation;
      } catch (e) {
        console.warn(
          "Backend unavailable, using simulated translation data.",
          e,
        );
        await new Promise((r) => setTimeout(r, 600));
        translationResult = `Simulated translation for: "${originalText}"`;
      }

      setTranslation(translationResult);

      let recsResult: RecommendationItem[] = [];
      try {
        const recResponse = await generateRecommendations({
          user_id: userId,
          original_text: originalText,
          translation: translationResult,
          source_language: profile.baseLanguage,
          target_language: profile.targetLanguage,
          context_scenario: selectedScenario.context,
        });
        recsResult = recResponse.recommendations;
      } catch (e) {
        console.warn(
          "Backend unavailable, using simulated recommendations.",
          e,
        );
        await new Promise((r) => setTimeout(r, 1200));
        recsResult = [
          {
            text: "This is a great phrase to use",
            score: 0.98,
            reason: "Perfectly matches the context intent.",
            usage: "Use it to sound a bit more casual.",
          },
          {
            text: "Here is an alternative",
            score: 0.85,
            reason: "A bit more formal.",
            usage: "Use it with strangers.",
          },
          {
            text: "Short version",
            score: 0.76,
            reason: "Quick and easy to remember.",
            usage: "When you are in a rush.",
          },
        ];
      }

      setRecommendations(recsResult);

      storePracticeSeed(originalText, translationResult, recsResult);
      onPredictedLevel("A1");
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unexpected error while processing request.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-12 pb-20 mt-12 sm:mt-16">
      <motion.header
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center space-y-6"
      >
        <p className="text-sm font-semibold text-indigo-400 uppercase tracking-widest">
          Live Translation Workspace
        </p>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-transparent bg-clip-text bg-linear-to-r from-white to-white/60">
          Translate With Context
        </h1>
        <p className="text-lg text-white/60 max-w-2xl mx-auto">
          Enter a sentence, choose a scenario, and the pipeline returns the
          translation plus ranked sentence suggestions you can reuse in
          practice.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <span className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium">
            {profile.baseLanguage.toUpperCase()} →{" "}
            {profile.targetLanguage.toUpperCase()}
          </span>
          <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/70 text-sm font-medium">
            Level {profile.currentLevel}
          </span>
          <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/70 text-sm font-medium">
            {selectedScenario.label}
          </span>
        </div>
      </motion.header>

      <div className="grid lg:grid-cols-2 gap-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-6"
        >
          <Card className="bg-black/20 border-white/10 backdrop-blur-md p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <p className="text-xs font-semibold text-white/50 uppercase tracking-widest">
                  Input
                </p>
                <h2 className="text-xl font-bold text-white mt-1">
                  Source Text
                </h2>
              </div>
              <span className="px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium">
                Context aware
              </span>
            </div>

            <form className="space-y-6" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="originalText" className="text-white/80">
                  Text to translate
                </Label>
                <Textarea
                  id="originalText"
                  name="originalText"
                  value={form.originalText}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      originalText: event.target.value,
                    }))
                  }
                  placeholder="Type the text you want to translate..."
                  rows={4}
                  className="bg-black/40 border-white/10 text-white text-base p-4 resize-none focus-visible:ring-indigo-500 transition-all hover:bg-black/60"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="contextScenario" className="text-white/80">
                  Context scenario
                </Label>
                <Select
                  value={form.contextScenario}
                  onValueChange={(val) =>
                    setForm((prev) => ({
                      ...prev,
                      contextScenario: val ?? prev.contextScenario,
                    }))
                  }
                >
                  <SelectTrigger className="bg-black/40 border-white/10 text-white">
                    <SelectValue placeholder="Select a scenario" />
                  </SelectTrigger>
                  <SelectContent className="bg-neutral-900 border-white/10 text-white">
                    {contextScenarios.map((scenario) => (
                      <SelectItem key={scenario.id} value={scenario.id}>
                        {scenario.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/10 space-y-3">
                <div>
                  <p className="text-xs text-indigo-300 font-medium">
                    Selected context
                  </p>
                  <p className="text-sm text-indigo-100 font-semibold mt-1">
                    {selectedScenario.label}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-indigo-200/70">
                  <span className="px-2 py-1 rounded bg-indigo-500/10 border border-indigo-500/10">
                    {selectedScenario.context.location}
                  </span>
                  <span className="px-2 py-1 rounded bg-indigo-500/10 border border-indigo-500/10">
                    {selectedScenario.context.environment}
                  </span>
                  <span className="px-2 py-1 rounded bg-indigo-500/10 border border-indigo-500/10">
                    {selectedScenario.context.sentiment}
                  </span>
                  <span className="px-2 py-1 rounded bg-indigo-500/10 border border-indigo-500/10">
                    {selectedScenario.context.intent}
                  </span>
                </div>
              </div>

              <Button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg hover:shadow-indigo-500/25 transition-all py-6 rounded-xl"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" /> Analyzing
                    Context...
                  </>
                ) : (
                  <>
                    <Languages className="w-5 h-5 mr-2" /> Translate & Get
                    Recommendations
                  </>
                )}
              </Button>

              {error && (
                <p className="text-sm font-medium text-red-400">{error}</p>
              )}
            </form>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-6 flex flex-col"
        >
          <Card className="bg-black/20 border-white/10 backdrop-blur-md p-6 flex-1 flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div>
                <p className="text-xs font-semibold text-white/50 uppercase tracking-widest">
                  Result
                </p>
                <h2 className="text-xl font-bold text-white mt-1">
                  Translation Output
                </h2>
              </div>
              {translation && (
                <span className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                  Ready for practice
                </span>
              )}
            </div>

            <div className="flex-1 flex flex-col justify-between space-y-6">
              {translation ? (
                <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                  <p className="text-xs text-white/40 font-medium mb-2">
                    Translation
                  </p>
                  <p className="text-lg text-white leading-relaxed font-medium">
                    {translation}
                  </p>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center p-8 rounded-xl bg-white/5 border border-white/5 border-dashed">
                  <p className="text-white/40 text-center text-sm">
                    Submit text to see the translation and unlock practice.
                  </p>
                </div>
              )}

              <Button
                type="button"
                variant="outline"
                onClick={() => onNavigate("practice")}
                disabled={!translation}
                className="w-full bg-transparent border-white/10 text-white hover:bg-white/10 transition-all py-6 rounded-xl group"
              >
                <BookOpen className="w-5 h-5 mr-2 text-white/50 group-hover:text-white transition-colors" />
                Continue to Practice
                <ArrowRight className="w-4 h-4 ml-2 text-white/50 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300" />
              </Button>
            </div>
          </Card>

          <AnimatePresence>
            {(recommendations.length > 0 || isSubmitting) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <RecommendationSection
                  recommendations={recommendations}
                  isLoading={isSubmitting}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
