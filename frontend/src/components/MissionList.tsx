"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { Activity, CheckCircle2, Clock, XCircle, ChevronDown, ChevronUp, Image as ImageIcon } from "lucide-react";
import { Card, Button } from "./ui";
import { ScreenshotModal } from "./ScreenshotModal";

type Execution = {
  id: string;
  account_id: string;
  status: string;
  orders_placed: number;
  screenshots: string[];
  error?: string;
  duration_seconds: number;
  ai_usage_count: number;
  ai_logs: string[];
  executed_at: string;
};

type Mission = {
  id: string;
  product_url: string;
  status: string;
  schedule_time: string;
  created_at: string;
  accounts: string[];
  variants: any[];
};

export function MissionList({ refreshTrigger }: { refreshTrigger: number }) {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [executions, setExecutions] = useState<Record<string, Execution[]>>({});
  const [loading, setLoading] = useState(true);
  
  // Modal state
  const [viewScreenshotPath, setViewScreenshotPath] = useState<string | null>(null);

  const fetchMissions = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://preorder-controller-678310400174.asia-southeast1.run.app";
      const res = await fetch(`${apiUrl}/missions`);
      const data = await res.json();
      setMissions(data.missions || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMissions();
    const interval = setInterval(fetchMissions, 15000); // Polling every 15s
    return () => clearInterval(interval);
  }, [refreshTrigger]);

  const toggleExpand = async (missionId: string) => {
    if (expandedId === missionId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(missionId);
    
    // Fetch executions if not already loaded
    if (!executions[missionId]) {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://preorder-controller-678310400174.asia-southeast1.run.app";
        const res = await fetch(`${apiUrl}/missions/${missionId}/results`);
        const data = await res.json();
        setExecutions(prev => ({ ...prev, [missionId]: data.executions || [] }));
      } catch (e) {
        console.error("Failed to load executions:", e);
      }
    }
  };

  const StatusBadge = ({ status }: { status: string }) => {
    switch(status) {
      case "scheduled": return <span className="flex items-center text-xs text-blue-400 bg-blue-950/30 px-2 py-1 rounded-full"><Clock className="w-3 h-3 mr-1"/> Scheduled</span>;
      case "in_progress": return <span className="flex items-center text-xs text-yellow-400 bg-yellow-950/30 px-2 py-1 rounded-full"><Activity className="w-3 h-3 mr-1"/> Running</span>;
      case "completed": return <span className="flex items-center text-xs text-emerald-400 bg-emerald-950/30 px-2 py-1 rounded-full"><CheckCircle2 className="w-3 h-3 mr-1"/> Success</span>;
      case "failed": return <span className="flex items-center text-xs text-rose-400 bg-rose-950/30 px-2 py-1 rounded-full"><XCircle className="w-3 h-3 mr-1"/> Failed</span>;
      default: return <span className="text-xs text-neutral-400">{status}</span>;
    }
  };

  if (loading) return <div className="text-center text-neutral-500 py-10 animate-pulse">Scanning operations logs...</div>;

  return (
    <>
      <div className="space-y-4">
        {missions.map(mission => (
          <Card key={mission.id} className="overflow-hidden border-neutral-800 transition-all hover:border-neutral-700">
            {/* Header */}
            <div 
              className="p-4 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between cursor-pointer bg-neutral-900/50 hover:bg-neutral-800/50 transition-colors"
              onClick={() => toggleExpand(mission.id)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-xs font-mono text-cyan-500">#{mission.id.substring(0,8)}</span>
                  <StatusBadge status={mission.status} />
                </div>
                <div className="text-sm text-neutral-300 truncate opacity-80">{mission.product_url}</div>
              </div>
              <div className="flex items-center gap-4 text-xs text-neutral-500 shrinks-0">
                <div className="text-right hidden sm:block">
                  <div className="text-neutral-400">Target Time</div>
                  <div>{format(new Date(mission.schedule_time), "MMM d, HH:mm:ss")}</div>
                </div>
                {expandedId === mission.id ? <ChevronUp className="w-5 h-5"/> : <ChevronDown className="w-5 h-5"/>}
              </div>
            </div>

            {/* Expanded Details */}
            {expandedId === mission.id && (
              <div className="p-4 border-t border-neutral-800 bg-black/20">
                <h4 className="text-xs uppercase tracking-wider text-neutral-500 mb-3">Execution Logs</h4>
                
                {executions[mission.id] ? (
                  executions[mission.id].length > 0 ? (
                    <div className="space-y-3">
                      {executions[mission.id].map(exec => (
                        <div key={exec.id} className="p-3 rounded border border-neutral-800 bg-[#0c0c0c] flex flex-col md:flex-row gap-4 justify-between">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-mono text-sm text-cyan-400">{exec.account_id}</span>
                              <span className={`text-xs ${exec.status === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>[{exec.status.toUpperCase()}]</span>
                              <span className="text-xs text-neutral-500">| {exec.duration_seconds}s</span>
                            </div>
                            <div className="text-xs text-neutral-400">
                              Orders: <span className="text-white">{exec.orders_placed}</span>
                            </div>
                            
                            {/* AI Fallback Logs */}
                            {exec.ai_usage_count > 0 && (
                              <div className="mt-2 text-xs border border-indigo-900/50 bg-indigo-950/20 p-2 rounded">
                                <span className="text-indigo-400 font-bold">🧠 AI Assists: {exec.ai_usage_count}</span>
                                <ul className="mt-1 space-y-1 text-indigo-300/80">
                                  {exec.ai_logs.map((log, i) => <li key={i}>- {log}</li>)}
                                </ul>
                              </div>
                            )}

                            {/* Error display */}
                            {exec.error && <div className="mt-2 text-xs text-rose-400 break-words">{exec.error}</div>}
                          </div>

                          {/* Screenshots */}
                          <div className="flex flex-col gap-2 justify-center">
                            {exec.screenshots && exec.screenshots.map((ss, i) => (
                              <Button 
                                key={i} 
                                variant="ghost" 
                                size="sm" 
                                className="text-xs border border-neutral-800 h-8"
                                onClick={(e) => { e.stopPropagation(); setViewScreenshotPath(ss); }}
                              >
                                <ImageIcon className="w-3 h-3 mr-2" /> View Image
                              </Button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-neutral-500 italic">No executions recorded yet. Worker may still be pending.</div>
                  )
                ) : (
                  <div className="animate-pulse text-sm text-neutral-600">Loading worker logs...</div>
                )}
              </div>
            )}
          </Card>
        ))}
        {missions.length === 0 && (
          <div className="text-center p-10 border border-dashed border-neutral-800 rounded-xl text-neutral-500">
            No missions found. Create one above to start sniping.
          </div>
        )}
      </div>

      {viewScreenshotPath && (
        <ScreenshotModal 
          blobPath={viewScreenshotPath} 
          onClose={() => setViewScreenshotPath(null)} 
        />
      )}
    </>
  );
}
