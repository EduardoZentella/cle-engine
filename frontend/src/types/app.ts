export type AppPage = "landing" | "translation" | "practice";

export interface UserProfile {
  username: string;
  baseLanguage: string;
  targetLanguage: string;
  currentLevel: string;
  city: string;
}

export type PracticeMode =
  | "match-pairs"
  | "complete-sentences"
  | "translate-full-sentences"
  | "complete-articles";

export interface PracticeSeed {
  originalText: string;
  translation: string;
  sourceLanguage: string;
  targetLanguage: string;
  currentLevel: string;
  contextLabel: string;
  recommendations: string[];
  generatedAt: string;
}
