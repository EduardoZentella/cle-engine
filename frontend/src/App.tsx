/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from "react";
import { NavigationDrawer } from "./menu/NavigationDrawer";
import { LandingPage } from "./landing/LandingPage";
import { TranslationPage } from "./translation/TranslationPage";
import { PracticePage } from "./practice/PracticePage";
import type { UserVerifyResponse } from "./services/api";
import { AnimatePresence, motion } from "motion/react";

import type { AppPage, UserProfile } from "./types/app";

export default function App() {
  // 1. Boot normally (do not auto-route to translation yet)
  const [currentPage, setCurrentPage] = useState<AppPage>("landing");

  // 2. Actually enforce the safeguard (start logged out, no mock ID)
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [userId, setUserId] = useState("");
  const [apiHealthy] = useState(true);

  const [profile, setProfile] = useState<UserProfile>({
    username: "",
    baseLanguage: "en",
    targetLanguage: "de",
    currentLevel: "A1",
    city: "",
  });

  // 3. THE INTERCEPT: Catch the Apple Shortcut payload on boot
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sharedText = params.get("text");

    if (sharedText) {
      // Put the text in the "waiting room"
      sessionStorage.setItem("cle_pending_translation", sharedText);
      // Clean the URL so it looks professional
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  // 4. THE SAFEGUARD: Handle login, then check the waiting room
  const handleLogin = (name: string, verifiedUser?: UserVerifyResponse) => {
    setIsLoggedIn(true);
    setUsername(name);

    if (verifiedUser?.user_id) {
      setUserId(verifiedUser.user_id);
    }

    setProfile((prev) => ({
      ...prev,
      username: name,
      ...(verifiedUser?.current_level && {
        currentLevel: verifiedUser.current_level,
      }),
      ...(verifiedUser?.target_language && {
        targetLanguage: verifiedUser.target_language,
      }),
      ...(verifiedUser?.base_language && {
        baseLanguage: verifiedUser.base_language,
      }),
      ...(verifiedUser?.city && { city: verifiedUser.city }),
    }));

    // Check if the user came from an Apple Shortcut deep link
    const pendingText = sessionStorage.getItem("cle_pending_translation");
    if (pendingText) {
      setCurrentPage("translation"); // Instantly route them to their goal
    } else {
      setCurrentPage("practice"); // Or wherever you normally route post-login
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setUsername("");
    setUserId("");
    setCurrentPage("landing");
  };

  const renderPage = () => {
    switch (currentPage) {
      case "translation":
        return (
          <TranslationPage
            userId={userId}
            profile={profile}
            onPredictedLevel={(level) =>
              setProfile((p) => ({ ...p, currentLevel: level }))
            }
            onNavigate={(page) => setCurrentPage(page as AppPage)}
          />
        );
      case "practice":
        return (
          <PracticePage
            userId={userId}
            onNavigate={(page) => setCurrentPage(page as AppPage)}
          />
        );
      case "landing":
      default:
        return (
          <LandingPage
            profile={profile}
            apiHealthy={apiHealthy}
            isLoggedIn={isLoggedIn}
            onNavigate={(page) => setCurrentPage(page as AppPage)}
          />
        );
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col bg-slate-950 text-slate-50 overflow-hidden font-sans">
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-900/20 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-900/20 blur-[120px] rounded-full pointer-events-none" />

      <NavigationDrawer
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        username={username}
        isLoggedIn={isLoggedIn}
        isSyncingSession={false}
        authError=""
        onLogin={handleLogin}
        onLogout={handleLogout}
      />

      <main className="relative z-10 flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-12">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentPage}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="w-full h-full"
          >
            {renderPage()}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
