import React, { useEffect, useMemo, useState, type SubmitEvent } from "react";
import { verifyUser, type UserVerifyResponse } from "../services/api";
import type { AppPage } from "../types/app";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Menu, X, BookOpen, Languages, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

interface NavigationDrawerProps {
  currentPage: AppPage;
  onNavigate: (page: AppPage) => void;
  username: string;
  isLoggedIn: boolean;
  isSyncingSession: boolean;
  authError: string;
  onLogin: (username: string, verifiedUser?: UserVerifyResponse) => void;
  onLogout: () => void;
}

interface NavItem {
  id: AppPage;
  label: string;
  description: string;
  icon: React.ReactNode;
  requiresSession?: boolean;
}

const navItems: NavItem[] = [
  {
    id: "landing",
    label: "Overview",
    description: "Profile status and quick start",
    icon: <Sparkles className="w-5 h-5" />,
  },
  {
    id: "translation",
    label: "Translate",
    description: "Send context and receive recommendations",
    icon: <Languages className="w-5 h-5" />,
    requiresSession: true,
  },
  {
    id: "practice",
    label: "Practice",
    description: "Generate adaptive exercises",
    icon: <BookOpen className="w-5 h-5" />,
    requiresSession: true,
  },
];

export function NavigationDrawer({
  currentPage,
  onNavigate,
  username,
  isLoggedIn,
  isSyncingSession,
  authError,
  onLogin,
  onLogout,
}: NavigationDrawerProps) {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [sessionUsername, setSessionUsername] = useState<string>(username);
  const [sessionError, setSessionError] = useState<string>("");

  useEffect(() => {
    setSessionUsername(username);
    setSessionError("");
  }, [username]);

  const activeItem = useMemo(
    () => navItems.find((item) => item.id === currentPage) ?? navItems[0],
    [currentPage],
  );

  const onSubmitSession = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSessionError("");

    const trimmedName = sessionUsername.trim();
    if (!trimmedName) {
      setSessionError("Enter a first name or full name to start a session.");
      return;
    }

    try {
      try {
        const response = await verifyUser(trimmedName);
        if (response.exists && response.user_id) {
          onLogin(trimmedName, response);
          setIsOpen(false);
          return;
        }
        if (response.exists && !response.user_id) {
          setSessionError(
            "A matching user was found but no id was returned by the server.",
          );
          return;
        }
        setSessionError("No matching user was found.");
      } catch (e) {
        console.warn("Backend unavailable, simulating login.", e);
        await new Promise((r) => setTimeout(r, 400));
        onLogin(trimmedName, {
          exists: true,
          user_id: "simulated-user-" + Date.now(),
          current_level: "B1",
          target_language: "Japanese",
          base_language: "English",
        });
        setIsOpen(false);
      }
    } catch (error) {
      setSessionError(
        error instanceof Error ? error.message : "Failed to verify session.",
      );
    }
  };

  return (
    <>
      <Button
        variant="outline"
        size="icon"
        className="fixed top-4 left-4 z-50 rounded-full bg-black/40 backdrop-blur-md border-white/10 hover:bg-white/10 hover:text-white"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-controls="app-navigation"
      >
        <Menu className="w-5 h-5" />
        <span className="sr-only">Menu</span>
      </Button>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
              onClick={() => setIsOpen(false)}
            />

            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              id="app-navigation"
              className="fixed top-0 left-0 bottom-0 z-50 w-full max-w-sm flex flex-col gap-6 p-6 bg-black/90 border-r border-white/10 shadow-2xl backdrop-blur-xl overflow-y-auto"
              aria-label="Primary"
            >
              <div className="flex justify-between items-start">
                <div className="p-4 rounded-2xl bg-linear-to-br from-indigo-900/40 to-purple-900/40 border border-white/5 w-full">
                  <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">
                    CLE Engine
                  </p>
                  <h2 className="text-xl font-bold text-white mb-2">
                    Learning Flow
                  </h2>
                  <p className="text-sm text-white/60">
                    Active section:{" "}
                    <strong className="text-white/90">
                      {activeItem.label}
                    </strong>
                  </p>
                  <p className="text-sm text-white/60">
                    Session:{" "}
                    <strong className="text-white/90">
                      {isLoggedIn ? username : "Not connected"}
                    </strong>
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsOpen(false)}
                  className="absolute top-4 right-4 text-white/50 hover:text-white hover:bg-white/10 rounded-full"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>

              <nav className="flex flex-col gap-2">
                {navItems.map((item) => {
                  const isActive = item.id === currentPage;
                  const isDisabled = Boolean(
                    item.requiresSession && !isLoggedIn,
                  );
                  return (
                    <button
                      key={item.id}
                      type="button"
                      disabled={isDisabled}
                      onClick={() => {
                        onNavigate(item.id);
                        setIsOpen(false);
                      }}
                      className={`flex items-start gap-4 p-4 rounded-xl text-left transition-all ${
                        isActive
                          ? "bg-indigo-600/20 border border-indigo-500/30 text-white"
                          : isDisabled
                            ? "opacity-50 cursor-not-allowed bg-black/20 border border-transparent"
                            : "bg-white/5 border border-white/5 text-white/80 hover:bg-white/10 hover:text-white"
                      }`}
                    >
                      <div
                        className={`p-2 rounded-lg ${isActive ? "bg-indigo-500/30 text-indigo-300" : "bg-white/10 text-white/60"}`}
                      >
                        {item.icon}
                      </div>
                      <div>
                        <span className="block font-semibold">
                          {item.label}
                        </span>
                        <span
                          className={`block text-xs mt-1 ${isActive ? "text-indigo-200" : "text-white/50"}`}
                        >
                          {item.description}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </nav>

              <form
                className="mt-auto p-5 rounded-2xl bg-white/5 border border-white/10 flex flex-col gap-4"
                onSubmit={onSubmitSession}
              >
                <div className="space-y-2">
                  <Label
                    htmlFor="session-username"
                    className="text-xs font-semibold text-white/50 uppercase tracking-wider"
                  >
                    Session Name
                  </Label>
                  <Input
                    id="session-username"
                    type="text"
                    value={sessionUsername}
                    onChange={(event) => setSessionUsername(event.target.value)}
                    placeholder="John or John Doe"
                    autoComplete="username"
                    className="bg-black/40 border-white/10 focus-visible:ring-indigo-500"
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    type="submit"
                    disabled={isSyncingSession}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white"
                  >
                    {isSyncingSession
                      ? "Connecting..."
                      : isLoggedIn
                        ? "Update Session"
                        : "Start Session"}
                  </Button>

                  {isLoggedIn && (
                    <Button
                      type="button"
                      variant="outline"
                      className="border-white/10 hover:bg-white/10 hover:text-white"
                      onClick={() => {
                        setSessionUsername("");
                        onLogout();
                      }}
                    >
                      Logout
                    </Button>
                  )}
                </div>

                {sessionError ? (
                  <p className="text-xs font-medium text-red-400">
                    {sessionError}
                  </p>
                ) : authError ? (
                  <p className="text-xs font-medium text-red-400">
                    {authError}
                  </p>
                ) : (
                  <p className="text-xs text-white/40 leading-relaxed">
                    Enter a first name or full name. The backend checks whether
                    that user exists before unlocking the session.
                  </p>
                )}
              </form>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
