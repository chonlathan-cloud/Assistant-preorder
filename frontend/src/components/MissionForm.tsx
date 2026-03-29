"use client";

import { useState } from "react";
import { Plus, X, Send } from "lucide-react";
import { Button, Card, Input } from "./ui";

export function MissionForm({ onMissionCreated }: { onMissionCreated: () => void }) {
  const [productUrl, setProductUrl] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [accounts, setAccounts] = useState<string[]>(["acc_1"]);
  const [variants, setVariants] = useState([{ name: "Classic Black", qty: 1 }]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const addVariant = () => setVariants([...variants, { name: "", qty: 1 }]);
  
  const removeVariant = (index: number) => {
    if (variants.length > 1) {
      setVariants(variants.filter((_, i) => i !== index));
    }
  };

  const updateVariant = (index: number, field: "name" | "qty", value: string | number) => {
    const newVariants = [...variants];
    newVariants[index] = { ...newVariants[index], [field]: value };
    setVariants(newVariants);
  };

  const toggleAccount = (acc: string) => {
    if (accounts.includes(acc)) {
      if (accounts.length > 1) setAccounts(accounts.filter((a) => a !== acc));
    } else {
      setAccounts([...accounts, acc]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://preorder-controller-678310400174.asia-southeast1.run.app";
      // Convert local datetime-local value to ISO string UTC
      const scheduleIso = scheduleTime ? new Date(scheduleTime).toISOString() : new Date().toISOString();

      const res = await fetch(`${apiUrl}/create-mission`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_url: productUrl,
          variants,
          schedule_time: scheduleIso,
          accounts,
        }),
      });

      if (!res.ok) throw new Error(await res.text());

      setProductUrl("");
      setVariants([{ name: "", qty: 1 }]);
      alert("Mission Scheduled!");
      onMissionCreated();
    } catch (err: any) {
      setError(err.message || "Failed to create mission");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6 border-cyan-900/50 bg-black/40 backdrop-blur-md">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2 text-cyan-400">
        <Send className="w-5 h-5" /> Schedule Mission
      </h2>
      
      {error && <div className="mb-4 p-3 bg-red-950/50 border border-red-900 text-red-400 rounded-md text-sm">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-neutral-400 uppercase tracking-wider mb-1">Product URL</label>
          <Input 
            required 
            type="url" 
            placeholder="https://s.lazada.co.th/..." 
            value={productUrl} 
            onChange={(e) => setProductUrl(e.target.value)} 
          />
        </div>

        <div>
          <label className="block text-xs text-neutral-400 uppercase tracking-wider mb-1">Execution Time</label>
          <Input 
            required 
            type="datetime-local" 
            value={scheduleTime} 
            onChange={(e) => setScheduleTime(e.target.value)} 
            className="w-full md:w-1/2"
          />
        </div>

        <div>
           <label className="block text-xs text-neutral-400 uppercase tracking-wider mb-2">Target Accounts</label>
           <div className="flex gap-2">
             {["acc_1", "acc_2"].map(acc => (
               <button
                 key={acc}
                 type="button"
                 onClick={() => toggleAccount(acc)}
                 className={`px-3 py-1.5 rounded-md border text-sm transition-colors ${
                   accounts.includes(acc) 
                    ? "bg-cyan-950 border-cyan-500 text-cyan-400" 
                    : "bg-neutral-900 border-neutral-800 text-neutral-500 hover:border-neutral-700"
                 }`}
               >
                 {acc.toUpperCase()}
               </button>
             ))}
           </div>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="block text-xs text-neutral-400 uppercase tracking-wider">Variants to Snipe</label>
            <Button type="button" variant="ghost" onClick={addVariant} className="h-8 px-2 py-1 text-xs text-cyan-400">
              <Plus className="w-3 h-3 mr-1" /> Add Variant
            </Button>
          </div>
          <div className="space-y-2">
            {variants.map((v, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input 
                  required 
                  placeholder="e.g. Classic Black" 
                  value={v.name} 
                  onChange={(e) => updateVariant(i, "name", e.target.value)}
                  className="flex-1"
                />
                <Input 
                  required 
                  type="number" 
                  min="1" 
                  value={v.qty} 
                  onChange={(e) => updateVariant(i, "qty", parseInt(e.target.value) || 1)}
                  className="w-20"
                />
                <Button type="button" variant="ghost" className="px-2 text-rose-500 hover:bg-rose-950/30" onClick={() => removeVariant(i)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>

        <Button type="submit" disabled={loading} className="w-full mt-6">
          {loading ? "Scheduling..." : "Deploy Sniper Mission"}
        </Button>
      </form>
    </Card>
  );
}
