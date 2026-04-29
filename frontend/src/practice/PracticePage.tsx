import React, { useEffect, useState } from "react";
import type { AppPage, PracticeMode, PracticeSeed } from "../types/app";
import {
  generatePracticeExercise,
  type PracticeExercise,
} from "../services/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Textarea } from "../../components/ui/textarea";
import {
  Loader2,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Lightbulb,
  BookOpen,
  Layers,
  Type,
  Hash,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

interface PracticePageProps {
  userId: string;
  onNavigate: (page: AppPage) => void;
}

const PRACTICE_SEED_STORAGE_KEY = "cle_engine_latest_practice_seed";

const practiceModes: Array<{
  mode: PracticeMode;
  title: string;
  description: string;
  accent: string;
  icon: React.ReactNode;
}> = [
  {
    mode: "match-pairs",
    title: "Match Pairs",
    description: "Connect source and target words.",
    accent:
      "from-indigo-500/20 to-violet-500/20 text-indigo-400 border-indigo-500/20 hover:border-indigo-500/50 hover:shadow-[0_0_30px_-5px_rgba(99,102,241,0.3)]",
    icon: <Layers className="w-8 h-8 mb-4" />,
  },
  {
    mode: "complete-sentences",
    title: "Complete Sentences",
    description: "Fill in the missing word.",
    accent:
      "from-emerald-500/20 to-teal-500/20 text-emerald-400 border-emerald-500/20 hover:border-emerald-500/50 hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.3)]",
    icon: <Type className="w-8 h-8 mb-4" />,
  },
  {
    mode: "translate-full-sentences",
    title: "Translate",
    description: "Type the full translation.",
    accent:
      "from-orange-500/20 to-amber-500/20 text-orange-400 border-orange-500/20 hover:border-orange-500/50 hover:shadow-[0_0_30px_-5px_rgba(249,115,22,0.3)]",
    icon: <BookOpen className="w-8 h-8 mb-4" />,
  },
  {
    mode: "complete-articles",
    title: "Articles",
    description: "Practice gendered articles.",
    accent:
      "from-fuchsia-500/20 to-pink-500/20 text-fuchsia-400 border-fuchsia-500/20 hover:border-fuchsia-500/50 hover:shadow-[0_0_30px_-5px_rgba(217,70,239,0.3)]",
    icon: <Hash className="w-8 h-8 mb-4" />,
  },
];

function getStoredPracticeSeed(): PracticeSeed | null {
  const rawSeed = sessionStorage.getItem(PRACTICE_SEED_STORAGE_KEY);
  return rawSeed ? (JSON.parse(rawSeed) as PracticeSeed) : null;
}

// Unified Generic Exercise Renderer
function ActiveExerciseView({
  exercise,
  onReset,
}: {
  exercise: PracticeExercise;
  onReset: () => void;
}) {
  const [selected, setSelected] = useState<string>("");
  const [revealed, setRevealed] = useState(false);

  const isCorrect =
    revealed &&
    selected.trim().toLowerCase() ===
      exercise.correct_answer?.trim().toLowerCase();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="max-w-2xl mx-auto"
    >
      <Card className="bg-black/40 border-white/10 backdrop-blur-xl p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 blur-[100px] pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-start justify-between mb-8 pb-6 border-b border-white/10">
            <div>
              <p className="text-xs font-semibold text-indigo-400 uppercase tracking-widest mb-2">
                Active Exercise
              </p>
              <h3 className="text-2xl font-bold text-white leading-tight">
                {exercise.prompt}
              </h3>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onReset}
              className="shrink-0 text-white/50 hover:text-white rounded-full bg-white/5 hover:bg-white/10"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </div>

          <div className="mb-8">
            {exercise.options.length > 0 ? (
              <div className="grid sm:grid-cols-2 gap-4">
                {exercise.options.map((opt) => {
                  const isSel = selected === opt;
                  const isRight = revealed && opt === exercise.correct_answer;
                  const isWrong = revealed && isSel && !isRight;

                  let btnState =
                    "bg-white/5 border-white/10 text-white hover:bg-white/10";
                  if (isSel && !revealed)
                    btnState =
                      "bg-indigo-600/20 border-indigo-500/50 text-white shadow-[0_0_15px_-3px_rgba(99,102,241,0.4)]";
                  if (isRight)
                    btnState =
                      "bg-emerald-500/20 border-emerald-500 text-emerald-100 shadow-[0_0_20px_-5px_rgba(16,185,129,0.4)]";
                  if (isWrong)
                    btnState =
                      "bg-red-500/20 border-red-500 text-red-100 shadow-[0_0_20px_-5px_rgba(239,68,68,0.4)] opacity-50";

                  return (
                    <button
                      key={opt}
                      type="button"
                      className={`relative p-5 rounded-2xl border text-center font-medium transition-all duration-300 ${btnState}`}
                      onClick={() => setSelected(opt)}
                      disabled={revealed}
                    >
                      {opt}
                      {isRight && (
                        <CheckCircle2 className="absolute top-1/2 right-4 -translate-y-1/2 w-5 h-5 text-emerald-400" />
                      )}
                      {isWrong && (
                        <XCircle className="absolute top-1/2 right-4 -translate-y-1/2 w-5 h-5 text-red-400" />
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <Textarea
                className="bg-black/40 border-white/20 text-white text-lg p-6 rounded-2xl min-h-37.5 focus-visible:ring-indigo-500 transition-all font-medium py-4 resize-none"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                placeholder="Type your answer here..."
                disabled={revealed}
              />
            )}
          </div>

          <div className="flex flex-col gap-6">
            {!revealed ? (
              <Button
                type="button"
                size="lg"
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-lg py-6 rounded-xl shadow-lg hover:shadow-indigo-500/25 transition-all"
                onClick={() => setRevealed(true)}
                disabled={!selected}
              >
                Check Answer
              </Button>
            ) : (
              <Button
                type="button"
                size="lg"
                className="w-full bg-white/10 hover:bg-white/20 text-white text-lg py-6 rounded-xl border border-white/10 transition-all"
                onClick={onReset}
              >
                Next Exercise
              </Button>
            )}

            <AnimatePresence>
              {revealed && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div
                    className={`p-6 rounded-2xl border ${
                      isCorrect
                        ? "bg-emerald-500/10 border-emerald-500/30"
                        : "bg-red-500/10 border-red-500/30"
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      {isCorrect ? (
                        <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="w-6 h-6 text-red-400 shrink-0 mt-0.5" />
                      )}
                      <div>
                        <h4
                          className={`text-lg font-bold mb-2 ${isCorrect ? "text-emerald-100" : "text-red-100"}`}
                        >
                          {isCorrect
                            ? "Perfect!"
                            : `Not quite. Correct answer: ${exercise.correct_answer}`}
                        </h4>
                        {exercise.explanation && (
                          <p className="text-white/80 leading-relaxed bg-black/20 p-4 rounded-xl text-sm border border-white/5 flex gap-3">
                            <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                            <span>{exercise.explanation}</span>
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

export function PracticePage({ userId, onNavigate }: PracticePageProps) {
  const [seed, setSeed] = useState<PracticeSeed | null>(null);
  const [activeExercise, setActiveExercise] = useState<PracticeExercise | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setSeed(getStoredPracticeSeed());
  }, []);

  const handleSelectMode = async (mode: PracticeMode) => {
    if (!seed) return;
    setIsLoading(true);
    try {
      try {
        const exercise = await generatePracticeExercise({
          user_id: userId,
          exercise_type: mode,
          original_text: seed.originalText,
          translation: seed.translation,
          source_language: seed.sourceLanguage,
          target_language: seed.targetLanguage,
          current_level: seed.currentLevel,
          context_label: seed.contextLabel,
          recommendations: seed.recommendations,
        });
        setActiveExercise(exercise);
      } catch (err) {
        console.warn(
          "Backend unavailable, using simulated practice exercises.",
          err,
        );
        await new Promise((r) => setTimeout(r, 800));

        let simulatedExercise: PracticeExercise;
        switch (mode) {
          case "match-pairs":
            simulatedExercise = {
              type: "match-pairs",
              prompt: `Match the translated concept to the source: "${seed.originalText}"`,
              options: [
                seed.translation,
                "Random choice 1",
                "Random choice 2",
                "Random choice 3",
              ],
              correct_answer: seed.translation,
              explanation: "This is the direct translation.",
            };
            break;
          case "complete-sentences":
            simulatedExercise = {
              type: "complete-sentences",
              prompt: `Complete the sentence based on your context: "${seed.contextLabel}"`,
              options: ["Option A", "Option B", "Option C"],
              correct_answer: "Option B",
              explanation:
                "Option B is correct because of the grammatical rules.",
            };
            break;
          case "translate-full-sentences":
            simulatedExercise = {
              type: "translate-full-sentences",
              prompt: `Translate this phrase to ${seed.targetLanguage} keeping the context in mind.`,
              options: [], // empty for text area
              correct_answer: seed.translation,
              explanation:
                "Checking your full typed translation against the suggested one.",
            };
            break;
          default:
            simulatedExercise = {
              type: mode,
              prompt: "Select the correct option:",
              options: ["Article 1", "Article 2", "Article 3"],
              correct_answer: "Article 2",
              explanation: "Specific rule for this article.",
            };
            break;
        }

        setActiveExercise(simulatedExercise);
      }
    } catch (err) {
      console.error("Failed to generate exercise", err);
      alert("Failed to generate exercise. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!seed) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6">
        <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-4">
          <BookOpen className="w-10 h-10 text-white/20" />
        </div>
        <h1 className="text-3xl font-bold text-white">
          No translation seed found
        </h1>
        <p className="text-white/60 max-w-md">
          Translate a sentence first to generate context-aware practice
          exercises based on your inputs.
        </p>
        <Button
          size="lg"
          className="mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-8 py-6 rounded-full shadow-lg"
          onClick={() => onNavigate("translation")}
        >
          Go to Translation
        </Button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto space-y-12 pb-20 mt-12 sm:mt-16">
      <motion.header
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center space-y-4"
      >
        <p className="text-sm font-semibold text-purple-400 uppercase tracking-widest">
          Practice Builder
        </p>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight">
          Interactive Practice
        </h1>
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-white/70 mt-4">
          <span>Based on your context:</span>
          <strong className="text-white">{seed.contextLabel}</strong>
        </div>
      </motion.header>

      {isLoading ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-24 space-y-6"
        >
          <div className="relative">
            <div className="absolute inset-0 bg-indigo-500 blur-xl opacity-20 rounded-full"></div>
            <Loader2 className="w-12 h-12 text-indigo-400 animate-spin relative z-10" />
          </div>
          <p className="text-xl font-medium text-white/60 animate-pulse">
            Generating personalized exercise...
          </p>
        </motion.div>
      ) : activeExercise ? (
        <ActiveExerciseView
          exercise={activeExercise}
          onReset={() => setActiveExercise(null)}
        />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="max-w-4xl mx-auto"
        >
          <div className="text-center mb-10">
            <h2 className="text-2xl font-semibold text-white">
              Select a format
            </h2>
            <p className="text-white/60 mt-2">
              Choose how you want to interact with your recent translations.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-6">
            {practiceModes.map((mode, index) => (
              <motion.button
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + index * 0.1 }}
                key={mode.mode}
                type="button"
                onClick={() => handleSelectMode(mode.mode)}
                className={`relative overflow-hidden group p-8 rounded-[2rem] border bg-linear-to-br bg-black/40 backdrop-blur-md text-left transition-all duration-500 outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-black ${mode.accent}`}
              >
                <div
                  className={`absolute inset-0 bg-linear-to-br ${mode.accent} opacity-0 group-hover:opacity-100 transition-opacity duration-500 mix-blend-screen pointer-events-none`}
                />
                <div className="relative z-10">
                  {mode.icon}
                  <h3 className="text-2xl font-bold text-white mb-2 tracking-tight group-hover:scale-[1.02] transition-transform origin-left">
                    {mode.title}
                  </h3>
                  <p className="text-white/60 text-lg leading-relaxed">
                    {mode.description}
                  </p>
                </div>
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
