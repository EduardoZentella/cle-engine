import type { RecommendationItem } from "../services/api";
import { Card } from "../../components/ui/card";
import { Sparkles, Activity, FileText } from "lucide-react";

interface RecommendationSectionProps {
  recommendations: RecommendationItem[];
  isLoading: boolean;
}

export function RecommendationSection({
  recommendations,
  isLoading,
}: RecommendationSectionProps) {
  if (isLoading) {
    return (
      <Card className="bg-black/20 border-white/10 backdrop-blur-md p-6">
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-xs font-semibold text-white/50 uppercase tracking-widest">
              Suggestions
            </p>
            <h2 className="text-xl font-bold text-white mt-1">
              Contextual Phrases
            </h2>
          </div>
          <div className="animate-pulse flex flex-col gap-4 mt-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-24 bg-white/5 rounded-xl border border-white/5"
              />
            ))}
          </div>
        </div>
      </Card>
    );
  }

  if (recommendations.length === 0) {
    return null;
  }

  return (
    <Card className="bg-black/20 border-white/10 backdrop-blur-md p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-xs font-semibold text-white/50 uppercase tracking-widest">
            Suggestions
          </p>
          <h2 className="text-xl font-bold text-white mt-1">
            Contextual Phrases
          </h2>
        </div>
        <span className="px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs font-medium flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5" />
          Scored & Ranked
        </span>
      </div>

      <ul className="flex flex-col gap-4">
        {recommendations.map((item, index) => (
          <li
            key={index}
            className="p-5 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group"
          >
            {/* Header: Phrase and Score */}
            <div className="flex justify-between items-start gap-4 mb-4">
              <p className="text-lg font-semibold text-white leading-snug">
                {item.text}
              </p>
              <span className="shrink-0 px-2.5 py-1 rounded-full bg-black/40 border border-white/5 text-xs font-medium text-white/70 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-indigo-400" />
                {(item.score * 100).toFixed(0)}% Match
              </span>
            </div>

            {/* Rich Context Display */}
            {(item.reason || item.usage) && (
              <div className="flex flex-col gap-4 pt-4 border-t border-white/10">
                {item.reason && (
                  <div className="flex items-start gap-3">
                    <div className="mt-1 p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 shrink-0">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-1">
                        Why use this?
                      </span>
                      <p className="text-sm text-white/80 leading-relaxed">
                        {item.reason}
                      </p>
                    </div>
                  </div>
                )}

                {item.usage && (
                  <div className="flex items-start gap-3">
                    <div className="mt-1 p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-1">
                        When to use
                      </span>
                      <p className="text-sm text-white/80 leading-relaxed">
                        {item.usage}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
