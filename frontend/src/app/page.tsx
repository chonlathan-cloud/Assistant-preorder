"use client";

import { useState } from "react";
import { MissionForm } from "@/components/MissionForm";
import { MissionList } from "@/components/MissionList";

export default function Dashboard() {
  const [trigger, setTrigger] = useState(0);

  const handleMissionCreated = () => {
    setTrigger(t => t + 1);
  };

  return (
    <main className="max-w-6xl mx-auto p-4 md:p-8">
      {/* Header */}
      <header className="mb-10 text-center md:text-left border-b border-neutral-800 pb-6">
        <h1 className="text-4xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-emerald-400 mb-2">
          TARGET ACQUIRED
        </h1>
        <p className="text-sm font-mono text-neutral-500 tracking-widest uppercase">
          Lazada Automated Sniper Ops // Mission Control
        </p>
      </header>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column - Form */}
        <div className="lg:col-span-5 hidden md:block">
          <div className="sticky top-8">
            <MissionForm onMissionCreated={handleMissionCreated} />
          </div>
        </div>

        {/* Mobile Form - Top of screen on mobile */}
        <div className="md:hidden">
          <MissionForm onMissionCreated={handleMissionCreated} />
        </div>

        {/* Right Column - Lists */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              Active Operations
              <span className="ml-3 relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
              </span>
            </h2>
          </div>
          <MissionList refreshTrigger={trigger} />
        </div>
      </div>
    </main>
  );
}
