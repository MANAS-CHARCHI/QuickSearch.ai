import React, { useState } from 'react';
import { Eye, EyeOff, ArrowRight, ShieldCheck, Mail, Lock, ArrowLeft, Sun, Moon, Check } from 'lucide-react';
import { AuthMode, UserProfile } from '../types';
import { AuthIllustration } from './AuthIllustration';

interface AuthViewProps {
  onLoginSuccess: (user: UserProfile) => void;
  isDark: boolean;
  onToggleTheme: () => void;
}

export const AuthView: React.FC<AuthViewProps> = ({
  onLoginSuccess,
  isDark,
  onToggleTheme,
}) => {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Switch modes cleanly
  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  const handleGoogleSignIn = () => {
    setIsLoading(true);
    setErrorMessage(null);
    // Simulate OAuth2 Google Sign-in flow
    setTimeout(() => {
      setIsLoading(false);
      onLoginSuccess({
        id: `usr-${Date.now()}`,
        email: 'alex.morgan@gmail.com',
        name: 'Alex Morgan',
        role: 'user',
      });
    }, 700);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!email.trim() || !email.includes('@')) {
      setErrorMessage('Please enter a valid email address.');
      return;
    }

    if (mode === 'forgot_password') {
      setIsLoading(true);
      setTimeout(() => {
        setIsLoading(false);
        setSuccessMessage(`Password reset link sent to ${email}. Check your inbox.`);
      }, 700);
      return;
    }

    if (!password || password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    if (mode === 'signup' && password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      onLoginSuccess({
        id: `usr-${Date.now()}`,
        email: email.trim(),
        name: email.split('@')[0],
        role: 'user',
      });
    }, 700);
  };

  return (
    <div className="min-h-screen bg-[#FFF9F4] dark:bg-[#140E0A] bg-grid-pattern text-stone-900 dark:text-[#FAF5F0] flex flex-col font-sans transition-colors duration-200">
      {/* Top Vault City Navbar (Identical to Main App) */}
      <header className="sticky top-0 z-40 bg-[#FFF9F4]/85 dark:bg-[#140E0A]/85 backdrop-blur-md border-b border-orange-200/50 dark:border-[#2D2118] transition-colors">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Brand (Identical to Main App) */}
          <div className="flex items-center space-x-2.5">
            <img src="/favicon.svg" alt="Vault City" className="w-6 h-6 rounded-lg shadow-xs shrink-0" />
            <span className="font-extrabold text-base tracking-tight text-stone-950 dark:text-white font-sans">
              vault city
            </span>
            <span className="text-[10px] text-stone-400 font-mono">/</span>
            <span className="text-[11px] text-stone-500 dark:text-stone-400 font-mono">auth</span>
            <span className="hidden sm:inline-block text-[9px] px-1.5 py-0.2 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 rounded font-mono border border-emerald-500/20">
              v1.0
            </span>
          </div>

          {/* Right Status & Controls (Identical to Main App) */}
          <div className="flex items-center space-x-2.5">
            <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-sans text-stone-500 dark:text-stone-400 bg-orange-50/60 dark:bg-[#1C1510] border border-orange-200/60 dark:border-[#2D2118]">
              <ShieldCheck className="w-3.5 h-3.5 text-stone-500 dark:text-stone-400" />
              <span>Encrypted</span>
            </div>

            {/* Quick Switch Mode Button */}
            {mode === 'login' ? (
              <button
                type="button"
                onClick={() => switchMode('signup')}
                className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold text-stone-700 dark:text-stone-300 hover:text-stone-950 dark:hover:text-white bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800 transition-colors cursor-pointer"
              >
                Sign up
              </button>
            ) : (
              <button
                type="button"
                onClick={() => switchMode('login')}
                className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold text-stone-700 dark:text-stone-300 hover:text-stone-950 dark:hover:text-white bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800 transition-colors cursor-pointer"
              >
                Log in
              </button>
            )}

            {/* Day / Night Theme Switcher */}
            <button
              onClick={onToggleTheme}
              title={isDark ? 'Switch to Day (Light)' : 'Switch to Night (Dark)'}
              className="p-1.5 rounded-md bg-stone-100 dark:bg-stone-900 border border-stone-200 dark:border-stone-800 text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white transition-all cursor-pointer font-mono"
            >
              {isDark ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center max-w-6xl mx-auto w-full px-4 py-6 md:py-8">
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
          {/* Left Column: Form Card */}
          <div className="lg:col-span-6 bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] rounded-2xl p-6 sm:p-7 shadow-val transition-all">
            {/* Title & Subtitle */}
            <div className="mb-6 space-y-1">
              {mode === 'forgot_password' && (
                <button
                  type="button"
                  onClick={() => switchMode('login')}
                  className="inline-flex items-center space-x-1 text-xs text-stone-500 hover:text-stone-900 dark:hover:text-white mb-2 transition-colors font-mono cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to Sign In</span>
                </button>
              )}
              <h2 className="text-lg sm:text-xl font-bold tracking-tight text-stone-900 dark:text-white font-mono">
                {mode === 'login' && 'Sign in to Vault City'}
                {mode === 'signup' && 'Create your account'}
                {mode === 'forgot_password' && 'Reset master password'}
              </h2>
              <p className="text-xs text-stone-500 dark:text-stone-400 font-sans">
                {mode === 'login' && 'Access your encrypted personal documents and records.'}
                {mode === 'signup' && 'Private, zero-knowledge storage for your identity & health files.'}
                {mode === 'forgot_password' && 'Enter your email to receive recovery instructions.'}
              </p>
            </div>

            {/* Error & Success Feedback */}
            {errorMessage && (
              <div className="mb-4 p-2.5 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-700 dark:text-rose-300 text-xs font-mono">
                {errorMessage}
              </div>
            )}
            {successMessage && (
              <div className="mb-4 p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-700 dark:text-emerald-300 text-xs font-mono flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            {/* Google OAuth2 Button (on Login & Signup) */}
            {mode !== 'forgot_password' && (
              <div className="space-y-4 mb-5">
                <button
                  type="button"
                  onClick={handleGoogleSignIn}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center space-x-2.5 py-2.5 px-4 bg-white dark:bg-[#181820] hover:bg-stone-50 dark:hover:bg-stone-900 border border-stone-200 dark:border-stone-700 rounded-xl text-xs font-semibold text-stone-800 dark:text-stone-100 transition-all cursor-pointer shadow-xs active:scale-[0.99]"
                >
                  {/* Google Multicolor Logo */}
                  <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                  <span>Continue with Google</span>
                </button>

                <div className="relative flex items-center justify-center">
                  <div className="border-t border-stone-200 dark:border-stone-800 w-full" />
                  <span className="bg-white dark:bg-[#1C1510] px-2.5 text-[10px] text-stone-400 font-mono uppercase tracking-wider relative">
                    or continue with email
                  </span>
                </div>
              </div>
            )}

            {/* Email / Password Form */}
            <form onSubmit={handleSubmit} className="space-y-3.5 font-mono">
              <div>
                <label className="block text-[11px] font-medium text-stone-700 dark:text-stone-300 mb-1">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@domain.com"
                    autoComplete="email"
                    className="w-full bg-stone-50 dark:bg-[#181820] border border-stone-200 dark:border-stone-700 rounded-lg pl-8 pr-3 py-2 text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-stone-400 dark:focus:border-stone-600 transition-colors font-mono"
                  />
                </div>
              </div>

              {mode !== 'forgot_password' && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] font-medium text-stone-700 dark:text-stone-300">
                      Master Password
                    </label>
                    {mode === 'login' && (
                      <button
                        type="button"
                        onClick={() => switchMode('forgot_password')}
                        className="text-[10px] text-stone-500 hover:text-stone-900 dark:hover:text-white transition-colors cursor-pointer"
                      >
                        Forgot password?
                      </button>
                    )}
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                      className="w-full bg-stone-50 dark:bg-[#181820] border border-stone-200 dark:border-stone-700 rounded-lg pl-8 pr-9 py-2 text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-stone-400 dark:focus:border-stone-600 transition-colors font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-200 p-0.5"
                    >
                      {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              )}

              {mode === 'signup' && (
                <div>
                  <label className="block text-[11px] font-medium text-stone-700 dark:text-stone-300 mb-1">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••••••"
                      autoComplete="new-password"
                      className="w-full bg-stone-50 dark:bg-[#181820] border border-stone-200 dark:border-stone-700 rounded-lg pl-8 pr-3 py-2 text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-stone-400 dark:focus:border-stone-600 transition-colors font-mono"
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full mt-2 py-2.5 px-4 bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-400 dark:text-stone-950 rounded-xl text-xs font-semibold font-sans transition-all cursor-pointer flex items-center justify-center space-x-1.5 shadow-sm active:scale-[0.99] disabled:opacity-50"
              >
                <span>
                  {isLoading
                    ? 'Processing...'
                    : mode === 'login'
                    ? 'Sign In to Vault'
                    : mode === 'signup'
                    ? 'Create Master Account'
                    : 'Send Reset Link'}
                </span>
                {!isLoading && <ArrowRight className="w-3.5 h-3.5" />}
              </button>
            </form>

            {/* Mode Switcher Footer */}
            <div className="mt-5 pt-4 border-t border-stone-100 dark:border-stone-800/80 text-center text-xs text-stone-500 font-sans">
              {mode === 'login' && (
                <p>
                  Don&apos;t have an account?{' '}
                  <button
                    type="button"
                    onClick={() => switchMode('signup')}
                    className="font-semibold text-stone-900 dark:text-white hover:underline cursor-pointer"
                  >
                    Sign up
                  </button>
                </p>
              )}
              {mode === 'signup' && (
                <p>
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => switchMode('login')}
                    className="font-semibold text-stone-900 dark:text-white hover:underline cursor-pointer"
                  >
                    Sign in
                  </button>
                </p>
              )}
              {mode === 'forgot_password' && (
                <p>
                  Remembered your password?{' '}
                  <button
                    type="button"
                    onClick={() => switchMode('login')}
                    className="font-semibold text-stone-900 dark:text-white hover:underline cursor-pointer"
                  >
                    Sign in
                  </button>
                </p>
              )}
            </div>

            {/* Mobile Val Town Code Illustration Card */}
            <div className="block lg:hidden mt-6 pt-5 border-t border-stone-200 dark:border-stone-800">
              <AuthIllustration />
            </div>
          </div>

          {/* Right Column: Val Town Style Live Animated Illustration Card (Desktop) */}
          <div className="hidden lg:flex flex-col space-y-4 lg:col-span-6">
            <AuthIllustration />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-5xl mx-auto px-4 py-4 text-center text-[11px] text-stone-400 font-mono">
        Vault City • Zero-Knowledge Personal Cloud • v1.0
      </footer>
    </div>
  );
};
